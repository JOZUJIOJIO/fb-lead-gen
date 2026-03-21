from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatMessage, Conversation, Lead, User
from app.routers.auth import get_current_user
from app.schemas import (
    AddChatMessage,
    ChatMessageResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationStats,
    ConversationUpdate,
)

router = APIRouter()


def _to_response(conv: Conversation, db: Session) -> ConversationResponse:
    lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
    msgs = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).order_by(ChatMessage.created_at).all()
    return ConversationResponse(
        id=conv.id,
        lead_id=conv.lead_id,
        profile_url=conv.profile_url or "",
        stage=conv.stage.value if hasattr(conv.stage, "value") else conv.stage,
        intent_score=conv.intent_score or 0,
        intent_signals=conv.intent_signals or [],
        turn_count=conv.turn_count or 0,
        max_turns=conv.max_turns or 10,
        whatsapp_pushed=conv.whatsapp_pushed or False,
        our_company=conv.our_company or "",
        our_products=conv.our_products or "",
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        lead_name=lead.name if lead else "",
        lead_company=lead.company if lead else "",
        messages=[ChatMessageResponse(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in msgs],
    )


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    stage: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if stage:
        query = query.filter(Conversation.stage == stage)
    convos = query.order_by(Conversation.updated_at.desc()).all()
    return [_to_response(c, db) for c in convos]


@router.post("", response_model=ConversationResponse)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Conversation).filter(
        Conversation.lead_id == data.lead_id,
        Conversation.user_id == current_user.id,
    ).first()
    if existing:
        return _to_response(existing, db)

    conv = Conversation(
        lead_id=data.lead_id,
        profile_url=data.profile_url,
        our_company=data.our_company,
        our_products=data.our_products,
        user_id=current_user.id,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _to_response(conv, db)


@router.get("/stats", response_model=ConversationStats)
def conversation_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convos = db.query(Conversation).filter(Conversation.user_id == current_user.id).all()
    stats = ConversationStats(total=len(convos))
    for c in convos:
        stage = c.stage.value if hasattr(c.stage, "value") else c.stage
        if hasattr(stats, stage):
            setattr(stats, stage, getattr(stats, stage) + 1)
        if c.whatsapp_pushed:
            stats.whatsapp_pushed += 1
    return stats


@router.get("/{conv_id}", response_model=ConversationResponse)
def get_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _to_response(conv, db)


@router.put("/{conv_id}", response_model=ConversationResponse)
def update_conversation(
    conv_id: int,
    data: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(conv, key, value)
    db.commit()
    db.refresh(conv)
    return _to_response(conv, db)


@router.post("/{conv_id}/messages", response_model=ChatMessageResponse)
def add_message(
    conv_id: int,
    data: AddChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msg = ChatMessage(conversation_id=conv_id, role=data.role, content=data.content)
    db.add(msg)
    if data.role == "us":
        conv.turn_count = (conv.turn_count or 0) + 1
    db.commit()
    db.refresh(msg)
    return ChatMessageResponse(id=msg.id, role=msg.role, content=msg.content, created_at=msg.created_at)


@router.post("/{conv_id}/ai-reply")
def ai_reply_suggestion(
    conv_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成回复建议。"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
    customer_message = data.get("customer_message", "")

    # 构建对话历史
    msgs = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id).order_by(ChatMessage.created_at).all()
    history = "\n".join(
        f"{'我方' if m.role == 'us' else '客户'}: {m.content}" for m in msgs
    )

    from app.services.ai_engine import generate_message
    suggestion = generate_message(
        lead_name=lead.name if lead else "Customer",
        lead_company=lead.company if lead else "",
        lead_data=lead.profile_data if lead else {},
        template_body=f"Based on conversation history:\n{history}\n\nCustomer's latest message: {customer_message}\n\nGenerate a natural follow-up reply.",
        language=lead.language if lead else "en",
    )
    return {"suggestion": suggestion}


@router.delete("/{conv_id}")
def delete_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id).delete()
    db.delete(conv)
    db.commit()
    return {"detail": "Conversation deleted"}
