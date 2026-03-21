from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Campaign, CampaignStatus, Lead, Message, MessageMode, MessageStatus, Template, User
from app.routers.auth import get_current_user
from app.schemas import CampaignCreate, CampaignResponse, CampaignUpdate
from app.services.ai_engine import generate_message
from app.services.whatsapp import generate_click_to_chat_link

router = APIRouter()


def _enrich_campaign(campaign: Campaign, db: Session) -> dict:
    message_count = db.query(Message).filter(Message.campaign_id == campaign.id).count()
    sent_count = (
        db.query(Message)
        .filter(Message.campaign_id == campaign.id, Message.status.in_(["sent", "delivered", "read", "replied"]))
        .count()
    )
    replied_count = (
        db.query(Message)
        .filter(Message.campaign_id == campaign.id, Message.status == "replied")
        .count()
    )
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        target_criteria=campaign.target_criteria,
        message_template_id=campaign.message_template_id,
        status=campaign.status.value if isinstance(campaign.status, CampaignStatus) else campaign.status,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        message_count=message_count,
        sent_count=sent_count,
        replied_count=replied_count,
    )


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaigns = db.query(Campaign).filter(Campaign.user_id == current_user.id).order_by(Campaign.created_at.desc()).all()
    return [_enrich_campaign(c, db) for c in campaigns]


@router.post("", response_model=CampaignResponse)
def create_campaign(
    data: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = Campaign(**data.model_dump(), user_id=current_user.id)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _enrich_campaign(campaign, db)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _enrich_campaign(campaign, db)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, key, value)
    db.commit()
    db.refresh(campaign)
    return _enrich_campaign(campaign, db)


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"detail": "Campaign deleted"}


@router.post("/{campaign_id}/launch")
def launch_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    template = None
    if campaign.message_template_id:
        template = db.query(Template).filter(Template.id == campaign.message_template_id).first()

    criteria = campaign.target_criteria or {}
    min_score = criteria.get("min_score", 60)
    status_filter = criteria.get("status", None)

    query = db.query(Lead).filter(Lead.user_id == current_user.id, Lead.score >= min_score)
    if status_filter:
        query = query.filter(Lead.status == status_filter)

    leads = query.all()
    messages_created = 0

    for lead in leads:
        existing = (
            db.query(Message)
            .filter(Message.lead_id == lead.id, Message.campaign_id == campaign.id)
            .first()
        )
        if existing:
            continue

        template_body = template.body if template else "Hi {{name}}, I'd like to connect with you about {{company}}."
        content = generate_message(
            lead_name=lead.name,
            lead_company=lead.company,
            lead_data=lead.profile_data,
            template_body=template_body,
            language=lead.language,
        )
        link = generate_click_to_chat_link(lead.phone, content) if lead.phone else ""

        msg = Message(
            lead_id=lead.id,
            campaign_id=campaign.id,
            content=content,
            mode=MessageMode.click_to_chat,
            click_to_chat_link=link,
            status=MessageStatus.pending_approval,
            user_id=current_user.id,
        )
        db.add(msg)
        messages_created += 1

    campaign.status = CampaignStatus.active
    db.commit()
    return {"messages_created": messages_created, "total_leads": len(leads)}
