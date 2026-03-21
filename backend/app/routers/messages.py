from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lead, Message, MessageStatus, Suppression, User
from app.routers.auth import get_current_user
from app.schemas import BatchIds, MessageListResponse, MessageResponse, MessageStats
from app.services.whatsapp import generate_click_to_chat_link, send_template_message

router = APIRouter()


def _to_response(msg: Message, db: Session) -> MessageResponse:
    lead = db.query(Lead).filter(Lead.id == msg.lead_id).first()
    return MessageResponse(
        id=msg.id,
        lead_id=msg.lead_id,
        campaign_id=msg.campaign_id,
        channel=msg.channel,
        content=msg.content,
        mode=msg.mode.value if hasattr(msg.mode, "value") else msg.mode,
        approved_by_user=msg.approved_by_user,
        click_to_chat_link=msg.click_to_chat_link or "",
        sent_at=msg.sent_at,
        delivered_at=msg.delivered_at,
        read_at=msg.read_at,
        replied_at=msg.replied_at,
        status=msg.status.value if hasattr(msg.status, "value") else msg.status,
        created_at=msg.created_at,
        lead_name=lead.name if lead else "",
        lead_company=lead.company if lead else "",
    )


@router.get("", response_model=MessageListResponse)
def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    campaign_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Message).filter(Message.user_id == current_user.id)
    if status:
        query = query.filter(Message.status == status)
    if campaign_id:
        query = query.filter(Message.campaign_id == campaign_id)

    total = query.count()
    items = query.order_by(Message.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return MessageListResponse(
        items=[_to_response(m, db) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{message_id}/approve", response_model=MessageResponse)
def approve_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = db.query(Message).filter(Message.id == message_id, Message.user_id == current_user.id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.approved_by_user = True
    msg.status = MessageStatus.approved
    db.commit()
    db.refresh(msg)
    return _to_response(msg, db)


@router.post("/{message_id}/send", response_model=MessageResponse)
def send_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = db.query(Message).filter(Message.id == message_id, Message.user_id == current_user.id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if not msg.approved_by_user:
        raise HTTPException(status_code=400, detail="Message must be approved before sending")

    lead = db.query(Lead).filter(Lead.id == msg.lead_id).first()
    if not lead or not lead.phone:
        raise HTTPException(status_code=400, detail="Lead has no phone number")

    suppressed = db.query(Suppression).filter(
        Suppression.contact == lead.phone, Suppression.user_id == current_user.id
    ).first()
    if suppressed:
        raise HTTPException(status_code=400, detail="Contact is in suppression list")

    if msg.mode.value == "click_to_chat" or msg.mode == "click_to_chat":
        msg.click_to_chat_link = generate_click_to_chat_link(lead.phone, msg.content)
        msg.status = MessageStatus.sent
        msg.sent_at = datetime.utcnow()
    else:
        try:
            send_template_message(lead.phone, msg.content)
            msg.status = MessageStatus.sent
            msg.sent_at = datetime.utcnow()
        except Exception as e:
            msg.status = MessageStatus.failed
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to send: {str(e)}")

    db.commit()
    db.refresh(msg)
    return _to_response(msg, db)


@router.post("/batch-approve")
def batch_approve(
    data: BatchIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msgs = db.query(Message).filter(Message.id.in_(data.ids), Message.user_id == current_user.id).all()
    approved = 0
    for msg in msgs:
        msg.approved_by_user = True
        msg.status = MessageStatus.approved
        approved += 1
    db.commit()
    return {"approved": approved}


@router.post("/batch-send")
def batch_send(
    data: BatchIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msgs = (
        db.query(Message)
        .filter(
            Message.id.in_(data.ids),
            Message.user_id == current_user.id,
            Message.approved_by_user == True,
        )
        .all()
    )
    sent = 0
    failed = 0
    for msg in msgs:
        lead = db.query(Lead).filter(Lead.id == msg.lead_id).first()
        if not lead or not lead.phone:
            failed += 1
            continue
        suppressed = db.query(Suppression).filter(
            Suppression.contact == lead.phone, Suppression.user_id == current_user.id
        ).first()
        if suppressed:
            failed += 1
            continue
        msg.click_to_chat_link = generate_click_to_chat_link(lead.phone, msg.content)
        msg.status = MessageStatus.sent
        msg.sent_at = datetime.utcnow()
        sent += 1
    db.commit()
    return {"sent": sent, "failed": failed}


@router.get("/stats", response_model=MessageStats)
def message_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msgs = db.query(Message).filter(Message.user_id == current_user.id).all()
    stats = MessageStats(total=len(msgs))
    for msg in msgs:
        status_val = msg.status.value if hasattr(msg.status, "value") else msg.status
        if hasattr(stats, status_val):
            setattr(stats, status_val, getattr(stats, status_val) + 1)
    return stats
