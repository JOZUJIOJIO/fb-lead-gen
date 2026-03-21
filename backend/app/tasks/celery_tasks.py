import logging
import time

from app.database import SessionLocal
from app.models import Lead, LeadStatus, Message, MessageStatus, Suppression
from app.services.ai_engine import analyze_lead
from app.services.whatsapp import generate_click_to_chat_link
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

MAX_SEND_PER_MINUTE = 10


@celery_app.task(bind=True, max_retries=3)
def analyze_leads_task(self, lead_ids: list[int]):
    """Background task to analyze multiple leads with AI."""
    db = SessionLocal()
    try:
        analyzed = 0
        for lead_id in lead_ids:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                continue
            try:
                result = analyze_lead(
                    name=lead.name,
                    company=lead.company,
                    profile_data=lead.profile_data,
                    email=lead.email,
                )
                lead.score = result["score"]
                lead.ai_analysis = result["analysis"]
                lead.language = result.get("language", lead.language)
                lead.status = LeadStatus.analyzed
                db.commit()
                analyzed += 1
            except Exception as e:
                logger.error(f"Failed to analyze lead {lead_id}: {e}")
                continue
        return {"analyzed": analyzed, "total": len(lead_ids)}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def send_messages_task(self, message_ids: list[int]):
    """Background task to send messages with rate limiting."""
    db = SessionLocal()
    try:
        sent = 0
        failed = 0
        for i, msg_id in enumerate(message_ids):
            if i > 0 and i % MAX_SEND_PER_MINUTE == 0:
                time.sleep(60)

            msg = db.query(Message).filter(Message.id == msg_id).first()
            if not msg or not msg.approved_by_user:
                failed += 1
                continue

            lead = db.query(Lead).filter(Lead.id == msg.lead_id).first()
            if not lead or not lead.phone:
                failed += 1
                continue

            suppressed = db.query(Suppression).filter(
                Suppression.contact == lead.phone,
                Suppression.user_id == msg.user_id,
            ).first()
            if suppressed:
                failed += 1
                continue

            try:
                msg.click_to_chat_link = generate_click_to_chat_link(lead.phone, msg.content)
                msg.status = MessageStatus.sent
                db.commit()
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send message {msg_id}: {e}")
                msg.status = MessageStatus.failed
                db.commit()
                failed += 1

        return {"sent": sent, "failed": failed}
    finally:
        db.close()
