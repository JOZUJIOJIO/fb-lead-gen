"""Campaigns router — CRUD + start/pause/stop."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Campaign, CampaignStatus, Lead, Message, PlatformEnum, User
from app.services.auth_service import get_current_user
from app.services.campaign_runner import run_campaign

logger = logging.getLogger(__name__)
router = APIRouter()

# Track running campaign tasks so we can cancel them
_running_tasks: dict[int, asyncio.Task] = {}


# ---------- Schemas ----------

class CampaignCreate(BaseModel):
    platform: str = "facebook"
    search_keywords: str
    search_region: str = ""
    search_industry: str = ""
    persona_id: Optional[int] = None
    send_limit: int = 20


class CampaignResponse(BaseModel):
    id: int
    platform: str
    search_keywords: Optional[str]
    search_region: Optional[str]
    search_industry: Optional[str]
    persona_id: Optional[int]
    send_limit: int
    status: str
    progress_current: int
    progress_total: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadBrief(BaseModel):
    id: int
    name: Optional[str]
    status: str
    profile_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignDetail(CampaignResponse):
    leads: list[LeadBrief] = []


# ---------- Endpoints ----------

@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = Campaign(
        platform=PlatformEnum(body.platform),
        search_keywords=body.search_keywords,
        search_region=body.search_region,
        search_industry=body.search_industry,
        persona_id=body.persona_id,
        send_limit=body.send_limit,
        status=CampaignStatus.draft,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("/", response_model=list[CampaignResponse])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Campaign).order_by(Campaign.created_at.desc())
    )
    return result.scalars().all()


@router.get("/stats/overview")
async def campaign_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dashboard stats."""
    total_campaigns = (await db.execute(select(func.count(Campaign.id)))).scalar() or 0
    active_campaigns = (
        await db.execute(
            select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.running)
        )
    ).scalar() or 0
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0

    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_leads": total_leads,
        "total_messages": total_messages,
    }


@router.get("/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.leads))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    leads_brief = [
        LeadBrief(
            id=l.id,
            name=l.name,
            status=l.status.value,
            profile_url=l.profile_url,
            created_at=l.created_at,
        )
        for l in campaign.leads
    ]
    return CampaignDetail(
        id=campaign.id,
        platform=campaign.platform.value,
        search_keywords=campaign.search_keywords,
        search_region=campaign.search_region,
        search_industry=campaign.search_industry,
        persona_id=campaign.persona_id,
        send_limit=campaign.send_limit,
        status=campaign.status.value,
        progress_current=campaign.progress_current,
        progress_total=campaign.progress_total,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        leads=leads_brief,
    )


@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if campaign.status == CampaignStatus.running:
        raise HTTPException(status_code=400, detail="任务已在运行中")

    # Launch as background asyncio task
    task = asyncio.create_task(run_campaign(campaign_id))
    _running_tasks[campaign_id] = task
    task.add_done_callback(lambda t: _running_tasks.pop(campaign_id, None))

    return {"message": "任务已启动", "campaign_id": campaign_id}


@router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if campaign.status != CampaignStatus.running:
        raise HTTPException(status_code=400, detail="任务未在运行中")

    campaign.status = CampaignStatus.paused
    await db.commit()
    return {"message": "任务已暂停", "campaign_id": campaign_id}


@router.post("/{campaign_id}/stop")
async def stop_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    campaign.status = CampaignStatus.failed
    await db.commit()

    # Cancel the running task if exists
    task = _running_tasks.pop(campaign_id, None)
    if task and not task.done():
        task.cancel()

    return {"message": "任务已停止", "campaign_id": campaign_id}


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    # Stop if running
    task = _running_tasks.pop(campaign_id, None)
    if task and not task.done():
        task.cancel()

    await db.delete(campaign)
    await db.commit()
