"""Auto-reply service — polls Messenger for incoming replies and responds."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.platforms.facebook import FacebookAdapter
from app.config import settings
from app.database import async_session
from app.models import (
    Campaign,
    Lead,
    LeadStatus,
    Message,
    MessageDirection,
    Persona,
    PlatformEnum,
)
from app.services.ai_service import generate_reply
from app.services.browser_lock import browser_lock

logger = logging.getLogger(__name__)

# Service state
_reply_task: asyncio.Task | None = None
_last_check_at: datetime | None = None
_is_running: bool = False


def get_status() -> dict:
    return {
        "running": _is_running,
        "last_check_at": _last_check_at.isoformat() if _last_check_at else None,
        "interval_seconds": settings.AUTO_REPLY_INTERVAL,
        "max_rounds": settings.AUTO_REPLY_MAX_ROUNDS,
    }


def start():
    global _reply_task, _is_running
    if _reply_task and not _reply_task.done():
        logger.info("Reply service already running")
        return
    _is_running = True
    _reply_task = asyncio.create_task(_reply_loop())
    logger.info("Reply service started (interval=%ds)", settings.AUTO_REPLY_INTERVAL)


def stop():
    global _reply_task, _is_running
    _is_running = False
    if _reply_task and not _reply_task.done():
        _reply_task.cancel()
    _reply_task = None
    logger.info("Reply service stopped")


async def _reply_loop():
    """Main polling loop — runs until stopped."""
    global _last_check_at, _is_running

    while _is_running:
        try:
            logger.info("Reply service: starting check cycle")
            await _check_and_reply()
            _last_check_at = datetime.utcnow()
            logger.info("Reply service: check cycle complete, next in %ds", settings.AUTO_REPLY_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Reply service: cancelled")
            break
        except Exception as e:
            logger.error("Reply service: error in check cycle: %s", e)

        # Wait for the configured interval
        try:
            await asyncio.sleep(settings.AUTO_REPLY_INTERVAL)
        except asyncio.CancelledError:
            break

    _is_running = False


async def _check_and_reply():
    """Single check cycle: scan Messenger, match leads, generate and send replies."""

    logger.info("Reply service: acquiring browser lock")
    async with browser_lock:
        logger.info("Reply service: browser lock acquired")

        adapter = FacebookAdapter()
        try:
            await adapter.initialize()

            # Verify Facebook login
            from app.services.campaign_runner import _verify_facebook_login
            login_ok = await _verify_facebook_login(adapter)
            if not login_ok:
                logger.error("Reply service: Facebook login expired, skipping cycle")
                return

            # Step 1: Get unread threads
            unread_threads = await adapter.get_unread_threads()
            if not unread_threads:
                logger.info("Reply service: no unread threads")
                return

            logger.info("Reply service: found %d unread thread(s)", len(unread_threads))

            async with async_session() as session:
                for thread in unread_threads:
                    try:
                        await _process_thread(session, adapter, thread)
                    except Exception as e:
                        logger.error(
                            "Reply service: error processing thread %s: %s",
                            thread.get("uid"), e,
                        )

        finally:
            await adapter.close()


async def _process_thread(
    session: AsyncSession,
    adapter: FacebookAdapter,
    thread: dict,
) -> None:
    """Process a single unread thread: match lead, read messages, reply."""

    uid = thread.get("uid", "")
    thread_name = thread.get("name", "unknown")
    thread_url = thread.get("thread_url", "")

    if not uid:
        return

    # Match to a lead we've messaged
    result = await session.execute(
        select(Lead)
        .where(
            Lead.platform_user_id == uid,
            Lead.platform == PlatformEnum.facebook,
            Lead.status.in_([LeadStatus.messaged, LeadStatus.replied]),
        )
        .order_by(Lead.created_at.desc())
        .limit(1)
    )
    lead = result.scalar_one_or_none()

    if lead is None:
        logger.debug("Reply service: thread %s (%s) has no matching lead, skipping", uid, thread_name)
        return

    # Check reply round count
    outbound_count = (await session.execute(
        select(func.count(Message.id)).where(
            Message.lead_id == lead.id,
            Message.direction == MessageDirection.outbound,
        )
    )).scalar() or 0

    if outbound_count >= settings.AUTO_REPLY_MAX_ROUNDS:
        logger.info(
            "Reply service: lead %d (%s) already at max rounds (%d), skipping",
            lead.id, thread_name, outbound_count,
        )
        return

    # Read the conversation
    conversation = await adapter.read_thread_messages(thread_url)
    if not conversation:
        logger.warning("Reply service: could not read messages from thread %s", uid)
        return

    # Check if the last message is from them (not us)
    if conversation[-1]["role"] != "user":
        logger.debug("Reply service: last message in thread %s is ours, skipping", uid)
        return

    # Save their new inbound message(s) to the database
    # Get existing messages to avoid duplicates
    existing_msgs = (await session.execute(
        select(Message)
        .where(Message.lead_id == lead.id)
        .order_by(Message.created_at.asc())
    )).scalars().all()

    existing_contents = {m.content for m in existing_msgs}

    new_inbound = []
    for msg in conversation:
        if msg["role"] == "user" and msg["content"] not in existing_contents:
            new_inbound.append(msg["content"])

    for content in new_inbound:
        inbound_msg = Message(
            lead_id=lead.id,
            direction=MessageDirection.inbound,
            content=content,
            ai_generated=False,
        )
        session.add(inbound_msg)

    if new_inbound:
        lead.status = LeadStatus.replied
        await session.commit()

    # Build conversation history for AI
    # Re-fetch all messages in order
    all_msgs = (await session.execute(
        select(Message)
        .where(Message.lead_id == lead.id)
        .order_by(Message.created_at.asc())
    )).scalars().all()

    history = []
    for m in all_msgs:
        role = "assistant" if m.direction == MessageDirection.outbound else "user"
        history.append({"role": role, "content": m.content})

    # Get persona with contact info
    campaign = (await session.execute(
        select(Campaign)
        .options(selectinload(Campaign.persona))
        .where(Campaign.id == lead.campaign_id)
    )).scalar_one_or_none()

    persona_dict = _build_persona_dict(campaign)

    # Get lead profile data
    lead_profile = lead.raw_profile_data if isinstance(lead.raw_profile_data, dict) else {}

    # Count current outbound for round tracking
    current_round = sum(1 for m in all_msgs if m.direction == MessageDirection.outbound) + 1

    # Generate AI reply
    logger.info(
        "Reply service: generating reply for lead %d (%s), round %d/%d",
        lead.id, thread_name, current_round, settings.AUTO_REPLY_MAX_ROUNDS,
    )

    try:
        reply_text = await generate_reply(
            conversation_history=history,
            persona=persona_dict,
            lead_profile=lead_profile,
            current_round=current_round,
            max_rounds=settings.AUTO_REPLY_MAX_ROUNDS,
        )
    except Exception as e:
        logger.error("Reply service: AI generation failed for lead %d: %s", lead.id, e)
        return

    if not reply_text:
        logger.warning("Reply service: empty reply for lead %d", lead.id)
        return

    # Send the reply
    profile_url = lead.profile_url or f"https://www.facebook.com/messages/t/{uid}"
    send_result = await adapter.send_message(profile_url, reply_text)

    if isinstance(send_result, dict):
        send_ok = send_result.get("success", False)
    else:
        send_ok = bool(send_result)

    if send_ok:
        outbound_msg = Message(
            lead_id=lead.id,
            direction=MessageDirection.outbound,
            content=reply_text,
            ai_generated=True,
        )
        session.add(outbound_msg)
        await session.commit()
        logger.info(
            "Reply service: replied to lead %d (%s), round %d: %s...",
            lead.id, thread_name, current_round, reply_text[:60],
        )
    else:
        failure_code = send_result.get("failure_code") if isinstance(send_result, dict) else None
        logger.error(
            "Reply service: send failed for lead %d (%s), code=%s",
            lead.id, thread_name, failure_code,
        )


def _build_persona_dict(campaign: Campaign | None) -> dict:
    """Build persona dict from campaign, including contact info."""
    if campaign is None or campaign.persona is None:
        return {"system_prompt": "你是一位友善的社交媒体用户，正在寻找志同道合的朋友。"}

    p = campaign.persona
    return {
        "name": p.name,
        "company_name": p.company_name,
        "company_description": p.company_description,
        "products": p.products,
        "salesperson_name": p.salesperson_name,
        "salesperson_title": p.salesperson_title,
        "tone": p.tone,
        "greeting_rules": p.greeting_rules,
        "conversation_rules": p.conversation_rules,
        "system_prompt": p.system_prompt,
        "whatsapp_id": p.whatsapp_id,
        "telegram_id": p.telegram_id,
    }
