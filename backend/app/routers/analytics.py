"""
Analytics router — feedback loop metrics.

Computes conversion funnel, source effectiveness, and trend data
from existing leads/conversations/messages tables. No extra models needed.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, cast, Date
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Conversation,
    ConversationStage,
    Lead,
    LeadSource,
    LeadStatus,
    Message,
    MessageStatus,
    User,
)
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/overview")
def analytics_overview(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full analytics overview with funnel, source breakdown, and trends."""
    since = datetime.utcnow() - timedelta(days=days)

    # --- Core counts ---
    total_leads = db.query(func.count(Lead.id)).filter(
        Lead.user_id == current_user.id
    ).scalar() or 0

    total_contacted = db.query(func.count(Lead.id)).filter(
        Lead.user_id == current_user.id,
        Lead.status.in_([LeadStatus.contacted, LeadStatus.replied, LeadStatus.converted]),
    ).scalar() or 0

    total_replied = db.query(func.count(Lead.id)).filter(
        Lead.user_id == current_user.id,
        Lead.status.in_([LeadStatus.replied, LeadStatus.converted]),
    ).scalar() or 0

    total_converted = db.query(func.count(Lead.id)).filter(
        Lead.user_id == current_user.id,
        Lead.status == LeadStatus.converted,
    ).scalar() or 0

    avg_score = db.query(func.avg(Lead.score)).filter(
        Lead.user_id == current_user.id,
        Lead.score > 0,
    ).scalar() or 0

    reply_rate = (total_replied / total_contacted * 100) if total_contacted > 0 else 0
    conversion_rate = (total_converted / total_leads * 100) if total_leads > 0 else 0

    # --- Leads by source ---
    source_rows = (
        db.query(Lead.source, func.count(Lead.id))
        .filter(Lead.user_id == current_user.id)
        .group_by(Lead.source)
        .all()
    )
    leads_by_source = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in source_rows}

    # --- Conversation stage funnel ---
    stage_rows = (
        db.query(Conversation.stage, func.count(Conversation.id))
        .filter(Conversation.user_id == current_user.id)
        .group_by(Conversation.stage)
        .all()
    )
    leads_by_stage = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in stage_rows}

    # --- Leads by country ---
    country_rows = (
        db.query(Lead.country, func.count(Lead.id))
        .filter(Lead.user_id == current_user.id, Lead.country != "")
        .group_by(Lead.country)
        .order_by(func.count(Lead.id).desc())
        .limit(10)
        .all()
    )
    leads_by_country = {row[0]: row[1] for row in country_rows}

    # --- Leads by industry ---
    industry_rows = (
        db.query(Lead.industry, func.count(Lead.id))
        .filter(Lead.user_id == current_user.id, Lead.industry != "")
        .group_by(Lead.industry)
        .order_by(func.count(Lead.id).desc())
        .limit(10)
        .all()
    )
    leads_by_industry = {row[0]: row[1] for row in industry_rows}

    # --- Daily activity (last N days) ---
    daily_leads = (
        db.query(
            cast(Lead.created_at, Date).label("date"),
            func.count(Lead.id),
        )
        .filter(Lead.user_id == current_user.id, Lead.created_at >= since)
        .group_by("date")
        .all()
    )
    daily_leads_map = {str(row[0]): row[1] for row in daily_leads}

    daily_contacted = (
        db.query(
            cast(Message.created_at, Date).label("date"),
            func.count(func.distinct(Message.lead_id)),
        )
        .filter(
            Message.user_id == current_user.id,
            Message.status.in_([MessageStatus.sent, MessageStatus.delivered, MessageStatus.read, MessageStatus.replied]),
            Message.created_at >= since,
        )
        .group_by("date")
        .all()
    )
    daily_contacted_map = {str(row[0]): row[1] for row in daily_contacted}

    daily_replied = (
        db.query(
            cast(Message.replied_at, Date).label("date"),
            func.count(func.distinct(Message.lead_id)),
        )
        .filter(
            Message.user_id == current_user.id,
            Message.replied_at.isnot(None),
            Message.replied_at >= since,
        )
        .group_by("date")
        .all()
    )
    daily_replied_map = {str(row[0]): row[1] for row in daily_replied}

    # Build daily array
    daily_activity = []
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        daily_activity.append({
            "date": date,
            "leads": daily_leads_map.get(date, 0),
            "contacted": daily_contacted_map.get(date, 0),
            "replied": daily_replied_map.get(date, 0),
        })

    return {
        "total_leads": total_leads,
        "total_contacted": total_contacted,
        "total_replied": total_replied,
        "total_converted": total_converted,
        "reply_rate": round(reply_rate, 1),
        "conversion_rate": round(conversion_rate, 1),
        "avg_score": round(float(avg_score), 1),
        "leads_by_source": leads_by_source,
        "leads_by_stage": leads_by_stage,
        "leads_by_country": leads_by_country,
        "leads_by_industry": leads_by_industry,
        "daily_activity": daily_activity,
    }


@router.get("/source-effectiveness")
def source_effectiveness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare effectiveness across lead sources."""
    rows = (
        db.query(
            Lead.source,
            func.count(Lead.id).label("total"),
            func.avg(Lead.score).label("avg_score"),
            func.sum(case((Lead.status == LeadStatus.replied, 1), else_=0)).label("replied"),
            func.sum(case((Lead.status == LeadStatus.converted, 1), else_=0)).label("converted"),
        )
        .filter(Lead.user_id == current_user.id)
        .group_by(Lead.source)
        .all()
    )

    results = []
    for row in rows:
        total = row.total or 0
        replied = row.replied or 0
        converted = row.converted or 0
        results.append({
            "source": str(row.source.value if hasattr(row.source, 'value') else row.source),
            "total": total,
            "avg_score": round(float(row.avg_score or 0), 1),
            "replied": replied,
            "converted": converted,
            "reply_rate": round(replied / total * 100, 1) if total > 0 else 0,
            "conversion_rate": round(converted / total * 100, 1) if total > 0 else 0,
        })

    return sorted(results, key=lambda x: x["conversion_rate"], reverse=True)


@router.get("/conversation-funnel")
def conversation_funnel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Conversation stage progression funnel."""
    stages = ["cold", "curious", "interested", "qualified", "ready_to_connect", "converted"]
    stage_counts = (
        db.query(Conversation.stage, func.count(Conversation.id))
        .filter(Conversation.user_id == current_user.id)
        .group_by(Conversation.stage)
        .all()
    )
    counts_map = {str(s[0].value if hasattr(s[0], 'value') else s[0]): s[1] for s in stage_counts}

    total = sum(counts_map.values()) if counts_map else 0
    funnel = []
    for stage in stages:
        count = counts_map.get(stage, 0)
        funnel.append({
            "stage": stage,
            "count": count,
            "percentage": round(count / total * 100, 1) if total > 0 else 0,
        })
    return funnel
