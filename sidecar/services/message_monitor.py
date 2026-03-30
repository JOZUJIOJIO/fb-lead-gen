"""Background message-monitoring service.

Polls the platform adapter every POLL_INTERVAL seconds for new inbound
messages, evaluates intent with the AI service, and takes the appropriate
action (reply, transfer, or stop).
"""

import asyncio
import logging
from typing import Optional

from db import Database
from adapters.base import PlatformAdapter
from services.ai_service import AIConfig, evaluate_intent, generate_reply
from services.notifier import emit_notification

logger = logging.getLogger(__name__)

# How long to wait between polling cycles (seconds).
POLL_INTERVAL = 5 * 60  # 5 minutes

# Lead statuses that should not receive further automated replies.
_TERMINAL_STATUSES = {"transferred", "rejected", "high_intent"}


class MessageMonitor:
    """Polls for new inbound messages and drives the AI reply / transfer flow."""

    def __init__(
        self,
        db: Database,
        adapter: PlatformAdapter,
        ai_config: AIConfig,
        poll_interval: int = POLL_INTERVAL,
    ) -> None:
        self._db = db
        self._adapter = adapter
        self._ai_config = ai_config
        self._poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background polling loop as an asyncio task."""
        if self._task and not self._task.done():
            logger.warning("MessageMonitor is already running.")
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(), name="message_monitor")
        logger.info("MessageMonitor started (poll_interval=%ds).", self._poll_interval)

    async def stop(self) -> None:
        """Cancel the background polling task and wait for it to finish."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("MessageMonitor stopped.")

    # -------------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Continuously poll for new messages until stopped."""
        while self._running:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("MessageMonitor poll error: %s", e, exc_info=True)

            # Wait before next poll (interruptible by stop())
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                raise

    async def _poll_once(self) -> None:
        """Run a single polling cycle: read messages and process each one."""
        logger.info("MessageMonitor: checking for new messages…")
        try:
            messages = await self._adapter.read_new_messages()
        except Exception as e:
            logger.error("read_new_messages failed: %s", e, exc_info=True)
            return

        if not messages:
            logger.info("MessageMonitor: no new messages.")
            return

        logger.info("MessageMonitor: processing %d new message(s).", len(messages))
        for msg in messages:
            try:
                await self._process_inbound_message(msg)
            except Exception as e:
                logger.error(
                    "Failed to process message from %s: %s",
                    msg.get("sender_id", "unknown"),
                    e,
                    exc_info=True,
                )

    # -------------------------------------------------------------------------
    # Per-message processing
    # -------------------------------------------------------------------------

    async def _process_inbound_message(self, msg: dict) -> None:
        """Handle a single inbound message dict from the adapter.

        Expected keys in *msg*:
            sender_id    – platform user ID of the sender
            sender_name  – display name
            content      – message text
            timestamp    – ISO-8601 string (may be empty)
        """
        sender_id: str = msg.get("sender_id", "").strip()
        sender_name: str = msg.get("sender_name", "未知用户")
        content: str = msg.get("content", "").strip()

        if not sender_id or not content:
            logger.debug("Skipping message with missing sender_id or content.")
            return

        # ------------------------------------------------------------------
        # 1. Match to an existing lead
        # ------------------------------------------------------------------
        lead = await self._find_lead_by_sender_id(sender_id)
        if lead is None:
            logger.info(
                "No lead found for sender_id=%s (%s). Ignoring.", sender_id, sender_name
            )
            return

        lead_id: int = lead["id"]
        lead_status: str = lead["status"]
        campaign_id: int = lead["campaign_id"]

        # ------------------------------------------------------------------
        # 2. Skip terminal statuses
        # ------------------------------------------------------------------
        if lead_status in _TERMINAL_STATUSES:
            logger.info(
                "Lead %d (status=%s) is in a terminal state. Skipping.", lead_id, lead_status
            )
            return

        # ------------------------------------------------------------------
        # 3. Save the inbound message to DB
        # ------------------------------------------------------------------
        await self._db.create_message(
            lead_id=lead_id,
            direction="inbound",
            content=content,
            ai_generated=False,
        )
        logger.info("Saved inbound message for lead %d.", lead_id)

        # ------------------------------------------------------------------
        # 4. Advance status to 'in_conversation' if currently 'messaged'
        # ------------------------------------------------------------------
        if lead_status == "messaged":
            await self._db.update_lead(lead_id, status="in_conversation")
            lead_status = "in_conversation"
            logger.info("Lead %d advanced to 'in_conversation'.", lead_id)

        # ------------------------------------------------------------------
        # 5. Build conversation history for AI
        # ------------------------------------------------------------------
        raw_history = await self._db.get_conversation(lead_id)
        conversation = [
            {
                "role": "user" if row["direction"] == "inbound" else "assistant",
                "content": row["content"] or "",
            }
            for row in raw_history
        ]

        # ------------------------------------------------------------------
        # 6. Load persona from campaign
        # ------------------------------------------------------------------
        persona = await self._load_persona(campaign_id)

        # ------------------------------------------------------------------
        # 7. Evaluate intent
        # ------------------------------------------------------------------
        try:
            decision = await evaluate_intent(conversation, persona, self._ai_config)
        except Exception as e:
            logger.error("evaluate_intent failed for lead %d: %s", lead_id, e, exc_info=True)
            return

        action: str = decision.get("action", "reply")
        reason: str = decision.get("reason", "")
        contact: Optional[str] = decision.get("contact")
        reply_text: Optional[str] = decision.get("reply")

        logger.info(
            "Lead %d: AI decision=%s reason=%s", lead_id, action, reason
        )

        # ------------------------------------------------------------------
        # 8. Act on decision
        # ------------------------------------------------------------------
        if action == "transfer":
            await self._handle_transfer(lead_id, sender_name, contact, reason)

        elif action == "stop":
            await self._handle_stop(lead_id, sender_name, reason)

        else:
            # action == "reply" (default)
            await self._handle_reply(lead_id, lead, reply_text, conversation, persona)

    # -------------------------------------------------------------------------
    # Action handlers
    # -------------------------------------------------------------------------

    async def _handle_transfer(
        self,
        lead_id: int,
        sender_name: str,
        contact: Optional[str],
        reason: str,
    ) -> None:
        """Mark lead as transferred and emit a Mac notification."""
        update_kwargs = {"status": "transferred"}
        if contact:
            update_kwargs["transfer_contact"] = contact

        await self._db.update_lead(lead_id, **update_kwargs)

        contact_info = contact or "（无联系方式）"
        emit_notification(
            title="潜在客户已转化 🎉",
            body=f"{sender_name} 表示兴趣，联系方式：{contact_info}",
            urgency="critical",
        )
        logger.info(
            "Lead %d transferred. Contact: %s. Reason: %s", lead_id, contact_info, reason
        )

    async def _handle_stop(
        self, lead_id: int, sender_name: str, reason: str
    ) -> None:
        """Mark lead as rejected."""
        await self._db.update_lead(lead_id, status="rejected")
        logger.info(
            "Lead %d (%s) marked as rejected. Reason: %s", lead_id, sender_name, reason
        )

    async def _handle_reply(
        self,
        lead_id: int,
        lead: dict,
        reply_text: Optional[str],
        conversation: list,
        persona: dict,
    ) -> None:
        """Send an AI-generated reply via the adapter and save it to DB."""
        # Use the reply the evaluator already generated, or generate a fresh one.
        if not reply_text:
            try:
                reply_text = await generate_reply(conversation, persona, self._ai_config)
            except Exception as e:
                logger.error(
                    "generate_reply failed for lead %d: %s", lead_id, e, exc_info=True
                )
                return

        profile_url: str = lead["profile_url"] or ""
        if not profile_url:
            logger.warning(
                "Lead %d has no profile_url; cannot send reply.", lead_id
            )
            return

        sent = await self._adapter.send_message(profile_url, reply_text)
        if sent:
            await self._db.create_message(
                lead_id=lead_id,
                direction="outbound",
                content=reply_text,
                ai_generated=True,
            )
            logger.info("Sent AI reply to lead %d (%d chars).", lead_id, len(reply_text))
        else:
            logger.warning("Failed to send reply to lead %d.", lead_id)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def _find_lead_by_sender_id(self, sender_id: str) -> Optional[dict]:
        """Return the most-recently-created lead matching *sender_id*, or None."""
        cursor = await self._db._conn.execute(
            """
            SELECT * FROM leads
            WHERE platform_user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (sender_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        # Convert aiosqlite.Row to plain dict for easier access
        return dict(row)

    async def _load_persona(self, campaign_id: int) -> dict:
        """Load the persona associated with *campaign_id*.

        Returns an empty dict if the campaign or persona cannot be found.
        """
        campaign = await self._db.get_campaign(campaign_id)
        if campaign is None:
            logger.warning("Campaign %d not found.", campaign_id)
            return {}

        persona_id = campaign["persona_id"]
        if not persona_id:
            return {}

        persona_row = await self._db.get_persona(persona_id)
        if persona_row is None:
            logger.warning("Persona %d not found.", persona_id)
            return {}

        return dict(persona_row)
