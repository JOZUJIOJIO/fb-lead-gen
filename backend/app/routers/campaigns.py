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
    name: str = ""
    platform: str = "facebook"
    search_keywords: str
    search_region: str = ""
    search_industry: str = ""
    persona_id: Optional[int] = None
    send_limit: int = 20
    max_per_hour: int = 10
    review_mode: bool = False
    send_hour_start: int = 9
    send_hour_end: int = 18
    timezone: str = "Asia/Shanghai"


class CampaignResponse(BaseModel):
    id: int
    name: Optional[str]
    platform: str
    search_keywords: Optional[str]
    search_region: Optional[str]
    search_industry: Optional[str]
    persona_id: Optional[int]
    send_limit: int
    max_per_hour: int
    review_mode: bool
    send_hour_start: int
    send_hour_end: int
    timezone: str
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
        name=body.name or body.search_keywords,
        platform=PlatformEnum(body.platform),
        search_keywords=body.search_keywords,
        search_region=body.search_region,
        search_industry=body.search_industry,
        persona_id=body.persona_id,
        send_limit=body.send_limit,
        max_per_hour=body.max_per_hour,
        review_mode=body.review_mode,
        send_hour_start=body.send_hour_start,
        send_hour_end=body.send_hour_end,
        timezone=body.timezone,
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
    """Dashboard stats with reply rates."""
    from app.models import LeadStatus

    total_campaigns = (await db.execute(select(func.count(Campaign.id)))).scalar() or 0
    active_campaigns = (
        await db.execute(
            select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.running)
        )
    ).scalar() or 0
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0

    # Reply stats
    messaged_count = (await db.execute(
        select(func.count(Lead.id)).where(Lead.status.in_([
            LeadStatus.messaged, LeadStatus.replied, LeadStatus.converted
        ]))
    )).scalar() or 0
    replied_count = (await db.execute(
        select(func.count(Lead.id)).where(Lead.status.in_([
            LeadStatus.replied, LeadStatus.converted
        ]))
    )).scalar() or 0
    converted_count = (await db.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.converted)
    )).scalar() or 0
    pending_review_count = (await db.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.pending_review)
    )).scalar() or 0
    skipped_count = (await db.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.rejected)
    )).scalar() or 0

    reply_rate = round((replied_count / messaged_count * 100), 1) if messaged_count > 0 else 0

    # Per-campaign stats
    campaign_stats_list = []
    campaigns_result = await db.execute(
        select(Campaign).order_by(Campaign.created_at.desc()).limit(10)
    )
    for c in campaigns_result.scalars().all():
        c_messaged = (await db.execute(
            select(func.count(Lead.id)).where(
                Lead.campaign_id == c.id,
                Lead.status.in_([LeadStatus.messaged, LeadStatus.replied, LeadStatus.converted])
            )
        )).scalar() or 0
        c_replied = (await db.execute(
            select(func.count(Lead.id)).where(
                Lead.campaign_id == c.id,
                Lead.status.in_([LeadStatus.replied, LeadStatus.converted])
            )
        )).scalar() or 0
        campaign_stats_list.append({
            "id": c.id,
            "name": c.name or c.search_keywords or "未命名",
            "messaged": c_messaged,
            "replied": c_replied,
            "reply_rate": round((c_replied / c_messaged * 100), 1) if c_messaged > 0 else 0,
        })

    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_leads": total_leads,
        "total_messages": total_messages,
        "messaged_count": messaged_count,
        "replied_count": replied_count,
        "converted_count": converted_count,
        "pending_review_count": pending_review_count,
        "skipped_count": skipped_count,
        "reply_rate": reply_rate,
        "campaign_stats": campaign_stats_list,
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
        name=campaign.name,
        platform=campaign.platform.value,
        search_keywords=campaign.search_keywords,
        search_region=campaign.search_region,
        search_industry=campaign.search_industry,
        persona_id=campaign.persona_id,
        send_limit=campaign.send_limit,
        max_per_hour=campaign.max_per_hour,
        review_mode=campaign.review_mode,
        send_hour_start=campaign.send_hour_start,
        send_hour_end=campaign.send_hour_end,
        timezone=campaign.timezone,
        status=campaign.status.value,
        progress_current=campaign.progress_current,
        progress_total=campaign.progress_total,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        leads=leads_brief,
    )


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    body: CampaignCreate,
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
        raise HTTPException(status_code=400, detail="运行中的任务无法编辑，请先暂停")

    campaign.name = body.name or body.search_keywords
    campaign.platform = PlatformEnum(body.platform)
    campaign.search_keywords = body.search_keywords
    campaign.search_region = body.search_region
    campaign.search_industry = body.search_industry
    campaign.persona_id = body.persona_id
    campaign.send_limit = body.send_limit
    campaign.max_per_hour = body.max_per_hour
    campaign.review_mode = body.review_mode
    campaign.send_hour_start = body.send_hour_start
    campaign.send_hour_end = body.send_hour_end
    campaign.timezone = body.timezone

    await db.commit()
    await db.refresh(campaign)
    return campaign


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

    # Pre-flight: check if Facebook cookies exist
    import json
    from pathlib import Path
    cookies_file = Path("/tmp/leadflow-browser/facebook_cookies.json")
    if not cookies_file.exists():
        raise HTTPException(
            status_code=400,
            detail="尚未导入 Facebook Cookies，请先在设置页面导入",
        )
    try:
        cookies = json.loads(cookies_file.read_text())
        fb_count = sum(1 for c in cookies if ".facebook.com" in c.get("domain", ""))
        if fb_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Cookies 中没有 Facebook 相关数据，请重新导入",
            )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Cookies 文件损坏，请重新导入")

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


# ---------- Review / Approve ----------

@router.get("/{campaign_id}/pending", response_model=list[LeadBrief])
async def get_pending_reviews(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get leads awaiting review for a campaign."""
    from app.models import LeadStatus
    result = await db.execute(
        select(Lead).where(
            Lead.campaign_id == campaign_id,
            Lead.status == LeadStatus.pending_review,
        ).order_by(Lead.created_at.desc())
    )
    leads = result.scalars().all()
    return [
        LeadBrief(
            id=l.id, name=l.name, status=l.status.value,
            profile_url=l.profile_url, created_at=l.created_at,
        ) for l in leads
    ]


class ReviewAction(BaseModel):
    lead_id: int
    action: str  # "approve" or "reject"


@router.post("/{campaign_id}/review")
async def review_lead_message(
    campaign_id: int,
    body: ReviewAction,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve or reject a pending message. Approved = send now."""
    from app.models import LeadStatus, Message, MessageDirection
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Lead).options(selectinload(Lead.messages))
        .where(Lead.id == body.lead_id, Lead.campaign_id == campaign_id)
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="线索不存在")
    if lead.status != LeadStatus.pending_review:
        raise HTTPException(status_code=400, detail="该线索不在待审核状态")

    if body.action == "reject":
        lead.status = LeadStatus.rejected
        await db.commit()
        return {"message": "已拒绝", "lead_id": lead.id}

    if body.action == "approve":
        # Find the pending outbound message
        pending_msg = None
        for m in lead.messages:
            if m.direction == MessageDirection.outbound:
                pending_msg = m
                break

        if not pending_msg:
            raise HTTPException(status_code=400, detail="没有待发送的消息")

        # Send via Facebook adapter
        from app.adapters.platforms.facebook import FacebookAdapter
        adapter = FacebookAdapter()
        try:
            await adapter.initialize()
            success = await adapter.send_message(lead.profile_url, pending_msg.content)
            if success:
                lead.status = LeadStatus.messaged
            else:
                lead.status = LeadStatus.failed
            await db.commit()
        except Exception as e:
            logger.error("Review approve: send failed for lead %d: %s", lead.id, e)
            lead.status = LeadStatus.failed
            await db.commit()
            raise HTTPException(status_code=500, detail=f"发送失败: {e}")
        finally:
            await adapter.close()

        return {"message": "已批准并发送", "lead_id": lead.id}

    raise HTTPException(status_code=400, detail="action 必须为 approve 或 reject")
