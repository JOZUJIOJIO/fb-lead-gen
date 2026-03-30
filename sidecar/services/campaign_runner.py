"""Campaign orchestrator — runs the search-analyze-message pipeline.

Each campaign runs as an asyncio.Task in the background. At most
MAX_CONCURRENT_CAMPAIGNS campaigns may run simultaneously.
"""

import asyncio
import logging
import random
from typing import Optional

from db import Database
from services.ai_service import AIConfig, analyze_profile, generate_greeting

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / module-level state
# ---------------------------------------------------------------------------

MAX_CONCURRENT_CAMPAIGNS = 2
DEFAULT_MAX_DAILY_MESSAGES = 50
DEFAULT_SEND_INTERVAL_MIN = 60   # seconds
DEFAULT_SEND_INTERVAL_MAX = 180  # seconds

# campaign_id -> asyncio.Task
_running_tasks: dict[int, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Public control functions
# ---------------------------------------------------------------------------

async def start_campaign(campaign_id: int, db: Database, ai_config: AIConfig) -> str:
    """Start a campaign background task.

    Returns a human-readable status string.
    Raises ValueError if the concurrent limit is hit or campaign is already running.
    """
    if campaign_id in _running_tasks and not _running_tasks[campaign_id].done():
        raise ValueError(f"Campaign {campaign_id} is already running")

    active = sum(1 for t in _running_tasks.values() if not t.done())
    if active >= MAX_CONCURRENT_CAMPAIGNS:
        raise ValueError(
            f"Cannot start campaign {campaign_id}: "
            f"already at the concurrent limit of {MAX_CONCURRENT_CAMPAIGNS}"
        )

    task = asyncio.create_task(
        _run_campaign(campaign_id, db, ai_config),
        name=f"campaign-{campaign_id}",
    )
    _running_tasks[campaign_id] = task
    logger.info("Campaign %d started (task created)", campaign_id)
    return f"Campaign {campaign_id} started"


async def pause_campaign(campaign_id: int, db: Database) -> str:
    """Mark campaign as paused in the DB.

    The running loop checks DB status between each target and will stop when
    it sees the 'paused' status.
    """
    await db.update_campaign(campaign_id, status="paused")
    logger.info("Campaign %d paused", campaign_id)
    return f"Campaign {campaign_id} paused"


async def stop_campaign(campaign_id: int, db: Database) -> str:
    """Cancel the asyncio task and mark campaign as failed/stopped in the DB."""
    await db.update_campaign(campaign_id, status="stopped")

    task: Optional[asyncio.Task] = _running_tasks.get(campaign_id)
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        logger.info("Campaign %d task cancelled", campaign_id)

    logger.info("Campaign %d stopped", campaign_id)
    return f"Campaign {campaign_id} stopped"


# ---------------------------------------------------------------------------
# Internal — the main pipeline
# ---------------------------------------------------------------------------

async def _run_campaign(campaign_id: int, db: Database, ai_config: AIConfig) -> None:
    """Main campaign loop: search → per-target (analyze → greet → send)."""
    adapter = None
    try:
        # ------------------------------------------------------------------
        # Load campaign + persona
        # ------------------------------------------------------------------
        campaign_row = await db.get_campaign(campaign_id)
        if campaign_row is None:
            logger.error("Campaign %d not found — aborting", campaign_id)
            return
        campaign = dict(campaign_row)

        persona: dict = {}
        persona_id = campaign.get("persona_id")
        if persona_id:
            persona_row = await db.get_persona(persona_id)
            if persona_row:
                persona = dict(persona_row)

        # ------------------------------------------------------------------
        # Transition to running
        # ------------------------------------------------------------------
        await db.update_campaign(campaign_id, status="running")
        logger.info("Campaign %d status → running", campaign_id)

        # ------------------------------------------------------------------
        # Read operational settings
        # ------------------------------------------------------------------
        proxy_server = await db.get_setting("proxy_server") or None

        max_daily_raw = await db.get_setting("max_daily_messages")
        max_daily = int(max_daily_raw) if max_daily_raw else DEFAULT_MAX_DAILY_MESSAGES

        interval_min_raw = await db.get_setting("send_interval_min")
        interval_min = float(interval_min_raw) if interval_min_raw else DEFAULT_SEND_INTERVAL_MIN

        interval_max_raw = await db.get_setting("send_interval_max")
        interval_max = float(interval_max_raw) if interval_max_raw else DEFAULT_SEND_INTERVAL_MAX

        send_limit: int = campaign.get("send_limit") or 50
        platform: str = campaign.get("platform", "facebook").lower()

        # ------------------------------------------------------------------
        # Initialize the platform adapter
        # ------------------------------------------------------------------
        if platform == "facebook":
            from adapters.facebook import FacebookAdapter
            adapter = FacebookAdapter(proxy_server=proxy_server)
        elif platform == "instagram":
            # Future: from adapters.instagram import InstagramAdapter
            # For now fall back to Facebook adapter
            from adapters.facebook import FacebookAdapter
            adapter = FacebookAdapter(proxy_server=proxy_server)
            logger.warning("Instagram adapter not implemented; using Facebook adapter")
        else:
            from adapters.facebook import FacebookAdapter
            adapter = FacebookAdapter(proxy_server=proxy_server)
            logger.warning("Unknown platform '%s'; defaulting to Facebook adapter", platform)

        await adapter.initialize()
        logger.info("Campaign %d: adapter initialized for platform=%s", campaign_id, platform)

        # ------------------------------------------------------------------
        # Search for people
        # ------------------------------------------------------------------
        keywords = campaign.get("search_keywords") or ""
        region = campaign.get("search_region") or ""
        industry = campaign.get("search_industry") or ""

        targets = await adapter.search_people(
            keywords=keywords,
            region=region,
            industry=industry,
        )
        logger.info("Campaign %d: search returned %d targets", campaign_id, len(targets))

        await db.update_campaign(campaign_id, progress_total=min(len(targets), send_limit))

        # ------------------------------------------------------------------
        # Per-target loop
        # ------------------------------------------------------------------
        sent_count = 0

        for target in targets:
            if sent_count >= send_limit:
                logger.info("Campaign %d: send_limit %d reached", campaign_id, send_limit)
                break

            # --- Pause / stop detection ---
            fresh_row = await db.get_campaign(campaign_id)
            if fresh_row is None:
                logger.warning("Campaign %d disappeared from DB — stopping", campaign_id)
                return
            current_status = dict(fresh_row).get("status")
            if current_status in ("paused", "stopped", "failed"):
                logger.info(
                    "Campaign %d detected status=%s — halting loop",
                    campaign_id, current_status,
                )
                return

            # --- Daily limit ---
            messages_today = await db.count_messages_today()
            if messages_today >= max_daily:
                logger.info(
                    "Campaign %d: daily limit %d reached (%d sent today) — stopping",
                    campaign_id, max_daily, messages_today,
                )
                await db.update_campaign(campaign_id, status="paused")
                return

            # --- Idempotency ---
            platform_user_id = target.get("platform_user_id", "")
            if platform_user_id and await db.lead_already_messaged(platform_user_id):
                logger.debug(
                    "Campaign %d: skipping already-messaged user %s",
                    campaign_id, platform_user_id,
                )
                continue

            # --- Process this target ---
            try:
                await _process_target(
                    campaign_id=campaign_id,
                    target=target,
                    persona=persona,
                    adapter=adapter,
                    db=db,
                    ai_config=ai_config,
                    platform=platform,
                )
                sent_count += 1
                await db.update_campaign(campaign_id, progress_current=sent_count)

            except asyncio.CancelledError:
                raise  # Let cancellation propagate
            except Exception as exc:
                logger.warning(
                    "Campaign %d: failed to process target %s — %s (continuing)",
                    campaign_id, target.get("name", "?"), exc,
                )

            # --- Human-like delay between sends ---
            if sent_count < send_limit:
                delay = random.uniform(interval_min, interval_max)
                logger.debug("Campaign %d: waiting %.1fs before next target", campaign_id, delay)
                await asyncio.sleep(delay)

        # ------------------------------------------------------------------
        # All targets processed — mark complete
        # ------------------------------------------------------------------
        await db.update_campaign(campaign_id, status="completed")
        logger.info("Campaign %d completed — %d messages sent", campaign_id, sent_count)

    except asyncio.CancelledError:
        logger.info("Campaign %d task was cancelled", campaign_id)
        raise
    except Exception as exc:
        logger.error("Campaign %d failed with unhandled error: %s", campaign_id, exc, exc_info=True)
        try:
            await db.update_campaign(campaign_id, status="failed")
        except Exception:
            pass
    finally:
        if adapter is not None:
            try:
                await adapter.close()
            except Exception as e:
                logger.warning("Campaign %d: error closing adapter: %s", campaign_id, e)


async def _process_target(
    campaign_id: int,
    target: dict,
    persona: dict,
    adapter,
    db: Database,
    ai_config: AIConfig,
    platform: str,
) -> None:
    """Analyze a single target and send them a greeting message."""
    profile_url = target.get("profile_url", "")
    platform_user_id = target.get("platform_user_id", "")
    name = target.get("name", "")

    logger.info("Campaign %d: processing target '%s' (%s)", campaign_id, name, platform_user_id)

    # Create lead record (status=found)
    lead_id = await db.create_lead(
        campaign_id=campaign_id,
        platform=platform,
        platform_user_id=platform_user_id,
        name=name,
        profile_url=profile_url,
        bio=target.get("snippet", ""),
    )

    # Fetch full profile
    profile_data = await adapter.get_profile(profile_url)

    # Merge snippet into profile_data if bio is missing
    if not profile_data.get("bio") and target.get("snippet"):
        profile_data["bio"] = target["snippet"]
    if not profile_data.get("name") and name:
        profile_data["name"] = name

    # AI: analyze profile (extract structured data from raw HTML)
    raw_html = profile_data.get("raw_html", "")
    analyzed: dict = {}
    if raw_html:
        try:
            analyzed = await analyze_profile(raw_html, ai_config)
        except Exception as exc:
            logger.warning("analyze_profile failed for %s: %s", name, exc)

    # Merge analyzed data into profile_data
    if analyzed:
        for key in ("name", "bio", "industry", "interests", "recent_topics", "work", "education"):
            if analyzed.get(key) and not profile_data.get(key):
                profile_data[key] = analyzed[key]

    # Update lead with richer data
    await db.update_lead(
        lead_id,
        bio=profile_data.get("bio", ""),
        industry=profile_data.get("industry", ""),
        profile_data=str(profile_data),
    )

    # AI: generate greeting
    greeting = await generate_greeting(profile_data, persona, ai_config)

    # Send the message
    success = await adapter.send_message(profile_url, greeting)

    if success:
        # Persist the outbound message
        await db.create_message(
            lead_id=lead_id,
            direction="outbound",
            content=greeting,
            ai_generated=True,
        )
        # Update lead status to messaged
        await db.update_lead(lead_id, status="messaged")
        logger.info("Campaign %d: message sent to '%s'", campaign_id, name)
    else:
        await db.update_lead(lead_id, status="failed")
        raise RuntimeError(f"send_message returned False for {name!r} ({profile_url!r})")
