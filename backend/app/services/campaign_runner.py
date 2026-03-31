"""Campaign orchestrator — runs the full search-analyze-message pipeline."""

import asyncio
import logging
import random
from datetime import datetime, date
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.platforms.facebook import FacebookAdapter
from app.config import settings
from app.database import async_session
from app.models import Campaign, CampaignStatus, Lead, LeadStatus, Message, MessageDirection, PlatformEnum
from app.services.ai_service import analyze_profile, generate_greeting

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _campaign_to_persona_dict(campaign: Campaign) -> dict:
    """Convert the campaign's linked Persona ORM object into a plain dict."""
    persona = campaign.persona
    if persona is None:
        return {"system_prompt": "你是一位友善的社交媒体用户，正在寻找志同道合的朋友。"}
    return {
        "name": persona.name,
        "company_name": persona.company_name,
        "company_description": persona.company_description,
        "products": persona.products,
        "salesperson_name": persona.salesperson_name,
        "salesperson_title": persona.salesperson_title,
        "tone": persona.tone,
        "greeting_rules": persona.greeting_rules,
        "conversation_rules": persona.conversation_rules,
        "system_prompt": persona.system_prompt,
    }


async def _wait_for_send_window(campaign: "Campaign") -> None:
    """If current time is outside the campaign's send window, sleep until it opens."""
    try:
        tz = ZoneInfo(campaign.timezone)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")

    while True:
        now = datetime.now(tz)
        hour = now.hour
        start, end = campaign.send_hour_start, campaign.send_hour_end

        if start <= end:
            in_window = start <= hour < end
        else:
            in_window = hour >= start or hour < end

        if in_window:
            return

        if start <= end:
            target_hour = start
        else:
            target_hour = start if hour < start else start

        wait_minutes = ((target_hour - hour) % 24) * 60 - now.minute
        if wait_minutes <= 0:
            wait_minutes = 1

        logger.info(
            "Campaign %d: outside send window (%02d:00-%02d:00 %s), current=%02d:%02d, waiting %d min",
            campaign.id, start, end, campaign.timezone, hour, now.minute, wait_minutes,
        )
        await asyncio.sleep(min(wait_minutes * 60, 300))


async def _is_already_contacted(session: AsyncSession, platform_user_id: str, platform: str) -> bool:
    """Check if this person has already been contacted in ANY campaign."""
    if not platform_user_id:
        return False
    result = await session.execute(
        select(Lead.id).where(
            Lead.platform_user_id == platform_user_id,
            Lead.platform == PlatformEnum(platform),
            Lead.status != LeadStatus.failed,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _get_today_sent_count(session: AsyncSession) -> int:
    """Count messages sent today across ALL campaigns."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await session.execute(
        select(func.count(Message.id)).where(
            Message.direction == MessageDirection.outbound,
            Message.created_at >= today_start,
        )
    )
    return result.scalar() or 0


async def _wait_for_daily_limit(session: AsyncSession, campaign_id: int) -> None:
    """If daily limit reached, wait until next day (re-check every 10 min)."""
    while True:
        sent_today = await _get_today_sent_count(session)
        if sent_today < settings.MAX_DAILY_MESSAGES:
            return

        logger.warning(
            "Campaign %d: daily limit reached (%d/%d), waiting for next day",
            campaign_id, sent_today, settings.MAX_DAILY_MESSAGES,
        )
        # Sleep 10 minutes, then re-check
        await asyncio.sleep(600)


async def _verify_facebook_login(adapter: FacebookAdapter) -> bool:
    """Check if Facebook cookies are valid by visiting facebook.com.

    Uses domcontentloaded instead of load — Facebook's homepage keeps loading
    background resources indefinitely, so waiting for 'load' frequently times
    out even when the page is perfectly usable and the user is logged in.

    Login failure is detected by inspecting the URL and page content for
    concrete login-page signals, NOT by treating a goto timeout as failure.
    """
    try:
        page = adapter._page
        if page is None:
            return False

        # Navigate with domcontentloaded — enough to read URL/title/content
        try:
            await page.goto(
                "https://www.facebook.com",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as nav_err:
            # Even if navigation times out, the page may still be usable.
            # Only bail out if we truly cannot reach the page at all.
            current_url = page.url or ""
            if "facebook.com" not in current_url:
                logger.error("Facebook login verification: cannot reach facebook.com: %s", nav_err)
                return False
            logger.warning(
                "Facebook login verification: navigation didn't fully complete (%s), "
                "but page URL is %s — continuing with check",
                nav_err, current_url,
            )

        await asyncio.sleep(2)

        url = (page.url or "").lower()
        title = (await page.title() or "").lower()

        # Concrete login-page signals
        login_url_patterns = ["/login", "login.php", "/checkpoint", "recover/initiate"]
        if any(pat in url for pat in login_url_patterns):
            logger.warning("Facebook login check: URL indicates login page: %s", url)
            return False

        if any(kw in title for kw in ["log in", "log into", "登录", "登入"]):
            logger.warning("Facebook login check: title indicates login page: %s", title)
            return False

        # Extra check: look for the login form in page content
        try:
            has_login_form = await page.evaluate(
                "() => !!(document.querySelector('#email') && document.querySelector('#pass'))"
            )
            if has_login_form:
                logger.warning("Facebook login check: login form detected in page")
                return False
        except Exception:
            pass  # Page might not be ready for JS evaluation; not a login failure

        return True
    except Exception as e:
        logger.error("Facebook login verification unexpected error: %s", e)
        return False


async def _refresh_campaign_status(session: AsyncSession, campaign_id: int) -> CampaignStatus:
    """Re-read the campaign status from DB (to detect pause/stop signals)."""
    result = await session.execute(
        select(Campaign.status).where(Campaign.id == campaign_id)
    )
    row = result.scalar_one_or_none()
    return row or CampaignStatus.failed


async def _get_already_processed_uids(session: AsyncSession, campaign_id: int) -> set[str]:
    """Get platform_user_ids already processed in this campaign (for resume)."""
    result = await session.execute(
        select(Lead.platform_user_id).where(
            Lead.campaign_id == campaign_id,
            Lead.platform_user_id.is_not(None),
        )
    )
    return {row for row in result.scalars().all() if row}


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_campaign(campaign_id: int) -> None:  # noqa: C901
    """Execute a full campaign: search -> analyze -> message.

    Supports:
    - Resume from interruption (skips already-processed leads)
    - Global deduplication across campaigns
    - Daily message limit enforcement
    - Send time window
    - Review mode (generate but don't send)
    - Cookie validation before start
    """
    logger.info("Campaign %d: starting", campaign_id)

    async with async_session() as session:
        # 1. Load campaign + persona
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            logger.error("Campaign %d not found", campaign_id)
            return

        if campaign.persona_id:
            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(Campaign)
                .options(selectinload(Campaign.persona))
                .where(Campaign.id == campaign_id)
            )
            campaign = result.scalar_one()

        persona_dict = _campaign_to_persona_dict(campaign)

        # Mark campaign as running
        campaign.status = CampaignStatus.running
        await session.commit()

        # 2. Initialize adapter + verify cookies
        adapter = FacebookAdapter()
        try:
            await adapter.initialize()
        except Exception as e:
            logger.error("Campaign %d: failed to initialize adapter: %s", campaign_id, e)
            campaign.status = CampaignStatus.failed
            await session.commit()
            return

        # 2b. Verify Facebook login
        login_ok = await _verify_facebook_login(adapter)
        if not login_ok:
            logger.error("Campaign %d: Facebook cookies expired or invalid — please re-import cookies", campaign_id)
            campaign.status = CampaignStatus.failed
            await session.commit()
            await adapter.close()
            return

        logger.info("Campaign %d: Facebook login verified", campaign_id)

        try:
            # 3. Search people
            search_results = await adapter.search_people(
                keywords=campaign.search_keywords or "",
                region=campaign.search_region or "",
                industry=campaign.search_industry or "",
            )

            if not search_results:
                logger.warning("Campaign %d: no search results found", campaign_id)
                campaign.status = CampaignStatus.completed
                campaign.progress_total = 0
                await session.commit()
                return

            # Cap to send_limit
            targets = search_results[: campaign.send_limit]
            campaign.progress_total = len(targets)

            # 3b. Get already-processed UIDs for resume
            already_processed = await _get_already_processed_uids(session, campaign_id)
            if already_processed:
                logger.info(
                    "Campaign %d: resuming — %d leads already processed",
                    campaign_id, len(already_processed),
                )

            await session.commit()

            # 4. Process each target
            sent_in_session = 0
            for idx, target in enumerate(targets):
                # Check if campaign was paused or stopped
                current_status = await _refresh_campaign_status(session, campaign_id)
                if current_status in (CampaignStatus.paused, CampaignStatus.failed):
                    logger.info("Campaign %d: stopped (status=%s)", campaign_id, current_status.value)
                    break

                profile_url = target.get("profile_url", "")
                target_name = target.get("name", "unknown")
                platform_uid = target.get("platform_user_id", "")

                # 4-pre-a. Resume: skip already processed in THIS campaign
                if platform_uid and platform_uid in already_processed:
                    logger.info("Campaign %d: SKIP %s (already processed, resuming)", campaign_id, target_name)
                    campaign.progress_current = idx + 1
                    await session.commit()
                    continue

                logger.info(
                    "Campaign %d: processing %d/%d — %s",
                    campaign_id, idx + 1, len(targets), target_name,
                )

                # 4-pre-b. Global dedup: skip if already contacted in other campaigns
                if await _is_already_contacted(session, platform_uid, "facebook"):
                    logger.info(
                        "Campaign %d: SKIP %s (already contacted in another campaign)",
                        campaign_id, target_name,
                    )
                    campaign.progress_current = idx + 1
                    await session.commit()
                    continue

                # 4a. Save as Lead (status=found)
                lead = Lead(
                    campaign_id=campaign_id,
                    platform=PlatformEnum.facebook,
                    platform_user_id=platform_uid,
                    name=target_name,
                    profile_url=profile_url,
                    status=LeadStatus.found,
                )
                session.add(lead)
                await session.commit()
                await session.refresh(lead)

                try:
                    # 4b. Get full profile (status=analyzing)
                    lead.status = LeadStatus.analyzing
                    await session.commit()

                    profile_data = await adapter.get_profile(profile_url)

                    # 4c. AI analysis
                    raw_html = profile_data.pop("raw_html", "")
                    ai_analysis = {}
                    if raw_html:
                        try:
                            ai_analysis = await analyze_profile(raw_html)
                        except Exception as e:
                            logger.warning("Campaign %d: AI analysis failed for %s: %s", campaign_id, target_name, e)

                    merged_profile = {**profile_data, **ai_analysis}
                    lead.bio = merged_profile.get("bio", "")[:500] if merged_profile.get("bio") else None
                    lead.industry = merged_profile.get("industry", "")[:100] if merged_profile.get("industry") else None
                    lead.raw_profile_data = merged_profile
                    await session.commit()

                    # 4d. Generate personalized greeting
                    try:
                        greeting = await generate_greeting(merged_profile, persona_dict)
                    except Exception as e:
                        logger.error("Campaign %d: greeting generation failed for %s: %s", campaign_id, target_name, e)
                        lead.status = LeadStatus.failed
                        profile_meta = lead.raw_profile_data or {}
                        if isinstance(profile_meta, dict):
                            profile_meta["failure_code"] = "greeting_generation_failed"
                            profile_meta["failure_step"] = "generate_greeting"
                            profile_meta["failure_detail"] = str(e)[:200]
                        lead.raw_profile_data = profile_meta
                        await session.commit()
                        continue

                    # 4e-pre. Wait for send window
                    await _wait_for_send_window(campaign)

                    # 4e-pre2. Check daily limit
                    if not campaign.review_mode:
                        await _wait_for_daily_limit(session, campaign_id)

                    # 4e. Send message (or queue for review)
                    if campaign.review_mode:
                        lead.status = LeadStatus.pending_review
                        msg = Message(
                            lead_id=lead.id,
                            direction=MessageDirection.outbound,
                            content=greeting,
                            ai_generated=True,
                        )
                        session.add(msg)
                        logger.info("Campaign %d: queued message for review — %s", campaign_id, target_name)
                    else:
                        send_result = await adapter.send_message(profile_url, greeting)
                        # send_message returns dict {"success": bool, "failure_code": str|None}
                        # or legacy bool for backward compat
                        if isinstance(send_result, dict):
                            send_ok = send_result.get("success", False)
                            failure_code = send_result.get("failure_code")
                        else:
                            send_ok = bool(send_result)
                            failure_code = "send_returned_false" if not send_ok else None

                        if send_ok:
                            lead.status = LeadStatus.messaged
                            msg = Message(
                                lead_id=lead.id,
                                direction=MessageDirection.outbound,
                                content=greeting,
                                ai_generated=True,
                            )
                            session.add(msg)
                            sent_in_session += 1
                        else:
                            # Record structured failure reason
                            profile_meta = lead.raw_profile_data or {}
                            if isinstance(profile_meta, dict):
                                profile_meta["failure_code"] = failure_code
                                profile_meta["failure_step"] = "send_message"
                            lead.raw_profile_data = profile_meta

                            # Check if send failure is due to login expiry
                            login_still_ok = await _verify_facebook_login(adapter)
                            if not login_still_ok:
                                logger.error(
                                    "Campaign %d: Facebook login expired mid-campaign! Pausing.",
                                    campaign_id,
                                )
                                lead.status = LeadStatus.failed
                                campaign.status = CampaignStatus.paused
                                await session.commit()
                                break
                            lead.status = LeadStatus.failed
                            logger.warning(
                                "Campaign %d: send failed for %s (code=%s)",
                                campaign_id, target_name, failure_code,
                            )

                    await session.commit()

                except Exception as e:
                    logger.error(
                        "Campaign %d: error processing lead %s: %s",
                        campaign_id, target_name, e,
                    )
                    lead.status = LeadStatus.failed
                    try:
                        profile_meta = lead.raw_profile_data or {}
                        if isinstance(profile_meta, dict):
                            profile_meta["failure_code"] = "processing_exception"
                            profile_meta["failure_step"] = "process_lead"
                            profile_meta["failure_detail"] = str(e)[:200]
                        lead.raw_profile_data = profile_meta
                    except Exception:
                        pass
                    await session.commit()

                # 4f. Update progress
                campaign.progress_current = idx + 1
                await session.commit()

                # 4g. Hourly rate limit: randomly distribute within the hour
                if idx < len(targets) - 1:
                    max_per_hour = campaign.max_per_hour or 10
                    base_interval = 3600.0 / max_per_hour
                    wait_secs = random.uniform(base_interval * 0.6, base_interval * 1.4)
                    logger.info(
                        "Campaign %d: waiting %.0fs before next target (max %d/hr)",
                        campaign_id, wait_secs, max_per_hour,
                    )
                    await asyncio.sleep(wait_secs)

            # 5. Mark campaign as completed (unless it was paused/stopped)
            final_status = await _refresh_campaign_status(session, campaign_id)
            if final_status == CampaignStatus.running:
                campaign.status = CampaignStatus.completed
                await session.commit()

            logger.info(
                "Campaign %d: finished (status=%s, sent_this_session=%d)",
                campaign_id, campaign.status.value, sent_in_session,
            )

        except Exception as e:
            logger.error("Campaign %d: unhandled error: %s", campaign_id, e)
            campaign.status = CampaignStatus.failed
            await session.commit()

        finally:
            await adapter.close()
