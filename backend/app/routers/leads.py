"""Leads router — query and manage leads."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Lead, LeadStatus, Message, PlatformEnum, User
from app.services.auth_service import get_current_user

router = APIRouter()


class MessageResponse(BaseModel):
    id: int
    direction: str
    content: str
    ai_generated: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LeadResponse(BaseModel):
    id: int
    campaign_id: int
    platform: str
    platform_user_id: Optional[str]
    name: Optional[str]
    bio: Optional[str]
    industry: Optional[str]
    profile_url: Optional[str]
    avatar_url: Optional[str]
    status: str
    raw_profile_data: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class LeadDetail(LeadResponse):
    messages: list[MessageResponse] = []


@router.get("/", response_model=list[LeadResponse])
async def list_leads(
    campaign_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Lead).order_by(Lead.created_at.desc())

    if campaign_id is not None:
        query = query.where(Lead.campaign_id == campaign_id)
    if status is not None:
        query = query.where(Lead.status == LeadStatus(status))
    if platform is not None:
        query = query.where(Lead.platform == PlatformEnum(platform))
    if search:
        query = query.where(Lead.name.ilike(f"%{search}%"))

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.messages))
        .where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="线索不存在")

    messages = [
        MessageResponse(
            id=m.id,
            direction=m.direction.value,
            content=m.content,
            ai_generated=m.ai_generated,
            created_at=m.created_at,
        )
        for m in lead.messages
    ]

    return LeadDetail(
        id=lead.id,
        campaign_id=lead.campaign_id,
        platform=lead.platform.value,
        platform_user_id=lead.platform_user_id,
        name=lead.name,
        bio=lead.bio,
        industry=lead.industry,
        profile_url=lead.profile_url,
        avatar_url=lead.avatar_url,
        status=lead.status.value,
        raw_profile_data=lead.raw_profile_data,
        created_at=lead.created_at,
        messages=messages,
    )


@router.patch("/{lead_id}/status")
async def update_lead_status(
    lead_id: int,
    new_status: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail="线索不存在")

    lead.status = LeadStatus(new_status)
    await db.commit()
    return {"message": "状态已更新", "lead_id": lead_id, "status": new_status}
