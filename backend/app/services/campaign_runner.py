"""Campaign orchestrator — runs the full search-analyze-message pipeline."""

import asyncio
import logging
import random
from datetime import datetime, date
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.adapters.platforms.facebook import FacebookAdapter
from app.config import settings
from app.database import async_session
from app.models import Campaign, CampaignStatus, Lead, LeadStatus, Message, MessageDirection, PlatformEnum
from app.services.ai_service import analyze_profile, generate_greeting
from app.services.browser_lock import browser_lock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Real-time progress tracking
# ---------------------------------------------------------------------------

_campaign_progress: dict[int, dict] = {}


def get_campaign_progress(campaign_id: int) -> dict | None:
    """Return live progress info for a running campaign, or None."""
    return _campaign_progress.get(campaign_id)


# Human-readable failure reason lookup
_FAILURE_REASONS: dict[str, str] = {
    "message_button_not_found": "目标页面没有找到「发消息」按钮",
    "message_input_not_found": "消息输入框未找到（重试和 Messenger 回退均失败）",
    "send_exception": "发送过程中发生异常",
    "send_returned_false": "发送函数返回失败",
    "greeting_generation_failed": "AI 问候语生成失败",
    "processing_exception": "处理流程异常",
    "platform_identity_verification": "Facebook 要求验证身份才能发送消息",
    "platform_action_restricted": "Facebook 限制了当前操作（异常活动检测）",
    "platform_feature_blocked": "Facebook 阻止使用此功能",
    "platform_temporarily_blocked": "Facebook 暂时封锁了发消息功能",
    "platform_messaging_blocked": "Facebook 阻止向此用户发送消息",
    "platform_unusual_activity": "Facebook 检测到异常活动",
    "platform_security_check": "Facebook 安全检查拦截",
    "platform_checkpoint_redirect": "Facebook 跳转到安全检查页面",
    "user_inactive": "非活跃用户：主页无近期发帖",
    "no_message_button": "用户主页无「发消息」按钮",
    "check_error": "消息能力检查失败",
}


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
        "output_language": persona.output_language,
    }


async def _wait_for_send_window(campaign: "Campaign") -> None:
    """If current time is outside the campaign's send window, sleep until it opens."""
    start, end = campaign.send_hour_start, campaign.send_hour_end

    # 0-24 or 0-0 means "always send"
    if (start == 0 and end >= 24) or (start == 0 and end == 0):
        return

    try:
        tz = ZoneInfo(campaign.timezone)
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")

    while True:
        now = datetime.now(tz)
        hour = now.hour

        if start <= end:
            in_window = start <= hour < end
        else:
            in_window = hour >= start or hour < end

        if in_window:
            return

        # Calculate minutes until the send window opens
        target = datetime.now(tz).replace(hour=start, minute=0, second=0, microsecond=0)
        if target <= now:
            # Window starts tomorrow
            from datetime import timedelta
            target += timedelta(days=1)
        wait_minutes = max(1, int((target - now).total_seconds() / 60))

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
            Lead.status.notin_([LeadStatus.failed, LeadStatus.blacklisted]),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _is_blacklisted(session: AsyncSession, platform_user_id: str, platform: str) -> bool:
    """Check if this person has been permanently blacklisted (inactive/no-messaging)."""
    if not platform_user_id:
        return False
    result = await session.execute(
        select(Lead.id).where(
            Lead.platform_user_id == platform_user_id,
            Lead.platform == PlatformEnum(platform),
            Lead.status == LeadStatus.blacklisted,
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
    logger.info("Campaign %d: waiting for browser lock", campaign_id)
    async with browser_lock:
        await _run_campaign_inner(campaign_id)


async def _run_campaign_inner(campaign_id: int) -> None:  # noqa: C901
    logger.info("Campaign %d: starting (browser lock acquired)", campaign_id)

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
            # 3. Collect all known UIDs (processed + blacklisted + contacted) for smart search
            already_processed = await _get_already_processed_uids(session, campaign_id)
            if already_processed:
                logger.info(
                    "Campaign %d: resuming — %d leads already processed",
                    campaign_id, len(already_processed),
                )

            # Collect globally known UIDs to skip during search
            all_known_uids = set(already_processed)
            from sqlalchemy import select as sa_select
            global_uids_result = await session.execute(
                sa_select(Lead.platform_user_id).where(
                    Lead.platform == PlatformEnum.facebook,
                    Lead.platform_user_id.is_not(None),
                )
            )
            for uid in global_uids_result.scalars().all():
                if uid:
                    all_known_uids.add(uid)

            # 3a. Multi-keyword: pick one random keyword to search
            raw_keywords = campaign.search_keywords or ""
            keyword_list = [k.strip() for k in raw_keywords.replace("，", ",").split(",") if k.strip()]
            if len(keyword_list) > 1:
                chosen_keyword = random.choice(keyword_list)
                logger.info(
                    "Campaign %d: multiple keywords detected (%d), randomly chose: '%s'",
                    campaign_id, len(keyword_list), chosen_keyword,
                )
            else:
                chosen_keyword = raw_keywords

            # 3b. Search — skips known UIDs and scrolls until enough new people found
            search_results = await adapter.search_people(
                keywords=chosen_keyword,
                region=campaign.search_region or "",
                industry=campaign.search_industry or "",
                known_uids=all_known_uids,
                target_new=campaign.send_limit,
            )

            # 3c. If no results, AI generates diverse keywords and retries (up to 5 rounds)
            if not search_results:
                tried_keywords = {chosen_keyword}
                from app.services.ai_service import _get_provider_config, _default_model, _call_openai_compatible, _call_anthropic

                for expand_round in range(5):
                    logger.info(
                        "Campaign %d: no new results, AI keyword expansion round %d/5",
                        campaign_id, expand_round + 1,
                    )
                    try:
                        provider, base_url, api_key = _get_provider_config()
                        model = _default_model(provider)
                        expand_prompt = (
                            f"I'm searching Facebook People to find potential business contacts.\n"
                            f"Original keyword: '{campaign.search_keywords or chosen_keyword}'\n"
                            f"Industry: {campaign.search_industry or 'any'}\n"
                            f"Region: {campaign.search_region or 'any'}\n"
                            f"Already tried (no results): {', '.join(sorted(tried_keywords))}\n\n"
                            f"Suggest ONE different Facebook search keyword to find real people "
                            f"in this industry. Be creative — try job titles, company types, "
                            f"industry terms, role names, or niche community terms. "
                            f"MUST be different from all tried keywords.\n"
                            f"Output ONLY the keyword (1-5 words), nothing else."
                        )
                        if provider == "anthropic":
                            expanded = await _call_anthropic(api_key, model, "You are a creative search keyword generator.", expand_prompt)
                        else:
                            expanded = await _call_openai_compatible(base_url, api_key, model, "You are a creative search keyword generator.", expand_prompt)
                        expanded = expanded.strip().strip('"').strip("'").strip()

                        # Skip if AI repeated a keyword
                        if expanded.lower() in {k.lower() for k in tried_keywords}:
                            logger.info("Campaign %d: AI repeated '%s', skipping", campaign_id, expanded)
                            continue

                        tried_keywords.add(expanded)
                        logger.info("Campaign %d: AI suggested keyword: '%s'", campaign_id, expanded)

                        search_results = await adapter.search_people(
                            keywords=expanded,
                            region=campaign.search_region or "",
                            industry=campaign.search_industry or "",
                            known_uids=all_known_uids,
                            target_new=campaign.send_limit,
                        )
                        if search_results:
                            chosen_keyword = expanded
                            break
                    except Exception as e:
                        logger.warning("Campaign %d: AI keyword expansion failed: %s", campaign_id, e)
                        break

            if not search_results:
                logger.warning("Campaign %d: no new results found (including AI expansion)", campaign_id)
                campaign.status = CampaignStatus.completed
                campaign.progress_total = 0
                await session.commit()
                return

            # Cap to send_limit
            targets = search_results[: campaign.send_limit]
            campaign.progress_total = len(targets)

            await session.commit()

            # 4. Process each target
            sent_in_session = 0
            for idx, target in enumerate(targets):
                # Check if campaign was paused or stopped
                current_status = await _refresh_campaign_status(session, campaign_id)
                if current_status in (CampaignStatus.paused, CampaignStatus.failed, CampaignStatus.stopped):
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

                # 4-pre-c. Blacklist: skip permanently blacklisted users
                if await _is_blacklisted(session, platform_uid, "facebook"):
                    logger.info(
                        "Campaign %d: SKIP %s (blacklisted — inactive or messaging blocked)",
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

                    _campaign_progress[campaign_id] = {
                        "current_lead_name": target_name,
                        "current_step": "访问主页提取资料",
                        "current_index": idx + 1,
                        "total": len(targets),
                    }
                    logger.info("Campaign %d: [%s] Step 1/4 — 访问主页提取资料...", campaign_id, target_name)
                    profile_data = await adapter.get_profile(profile_url)
                    logger.info(
                        "Campaign %d: [%s] Step 1/4 完成 — name=%s, bio=%s, work=%s",
                        campaign_id, target_name,
                        profile_data.get("name", "?"),
                        (profile_data.get("bio") or "")[:50],
                        (profile_data.get("work") or "")[:50],
                    )

                    # 4c. AI analysis
                    raw_html = profile_data.pop("raw_html", "")
                    ai_analysis = {}
                    if raw_html:
                        _campaign_progress[campaign_id] = {
                            "current_lead_name": target_name,
                            "current_step": "AI分析",
                            "current_index": idx + 1,
                            "total": len(targets),
                        }
                        logger.info("Campaign %d: [%s] Step 2/4 — AI 分析用户资料...", campaign_id, target_name)
                        try:
                            ai_analysis = await analyze_profile(raw_html)
                            logger.info(
                                "Campaign %d: [%s] Step 2/4 完成 — industry=%s, interests=%s",
                                campaign_id, target_name,
                                ai_analysis.get("industry", "?"),
                                str(ai_analysis.get("interests", ""))[:50],
                            )
                        except Exception as e:
                            logger.warning("Campaign %d: [%s] Step 2/4 AI 分析失败(继续): %s", campaign_id, target_name, e)
                    else:
                        logger.info("Campaign %d: [%s] Step 2/4 跳过 — 无 HTML 数据", campaign_id, target_name)

                    merged_profile = {**profile_data, **ai_analysis}
                    lead.bio = merged_profile.get("bio", "")[:500] if merged_profile.get("bio") else None
                    lead.industry = merged_profile.get("industry", "")[:100] if merged_profile.get("industry") else None
                    lead.raw_profile_data = merged_profile
                    await session.commit()

                    # 4c-2. Activity check (soft — log only, don't blacklist for missing posts)
                    recent_posts = merged_profile.get("recent_posts", [])
                    if recent_posts:
                        logger.info("Campaign %d: [%s] 活跃用户 — %d 条近期帖子", campaign_id, target_name, len(recent_posts))
                    else:
                        logger.info("Campaign %d: [%s] 未检测到帖子（可能是页面未完全加载），继续处理", campaign_id, target_name)

                    # 4d. Generate personalized greeting
                    _campaign_progress[campaign_id] = {
                        "current_lead_name": target_name,
                        "current_step": "生成问候语",
                        "current_index": idx + 1,
                        "total": len(targets),
                    }
                    logger.info("Campaign %d: [%s] Step 3/4 — AI 生成个性化问候语...", campaign_id, target_name)
                    try:
                        greeting = await generate_greeting(merged_profile, persona_dict)
                        logger.info("Campaign %d: [%s] Step 3/4 完成 — 消息: %s...", campaign_id, target_name, greeting[:60])
                    except Exception as e:
                        logger.error("Campaign %d: greeting generation failed for %s: %s", campaign_id, target_name, e)
                        lead.status = LeadStatus.failed
                        profile_meta = lead.raw_profile_data or {}
                        if isinstance(profile_meta, dict):
                            profile_meta["failure_code"] = "greeting_generation_failed"
                            profile_meta["failure_step"] = "generate_greeting"
                            profile_meta["failure_detail"] = str(e)[:200]
                        lead.raw_profile_data = profile_meta
                        flag_modified(lead, "raw_profile_data")
                        await session.commit()
                        continue

                    # 4e-pre. Wait for send window
                    await _wait_for_send_window(campaign)

                    # 4e-pre2. Check daily limit
                    if not campaign.review_mode:
                        await _wait_for_daily_limit(session, campaign_id)

                    # 4e. Send message (or queue for review)
                    _campaign_progress[campaign_id] = {
                        "current_lead_name": target_name,
                        "current_step": "发送消息",
                        "current_index": idx + 1,
                        "total": len(targets),
                    }
                    logger.info("Campaign %d: [%s] Step 4/4 — 发送消息...", campaign_id, target_name)
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
                            is_platform_restriction = (
                                failure_code and failure_code.startswith("platform_")
                            )
                            profile_meta = lead.raw_profile_data or {}
                            if isinstance(profile_meta, dict):
                                profile_meta["failure_code"] = failure_code
                                profile_meta["failure_step"] = "send_message"
                                profile_meta["failure_reason"] = _FAILURE_REASONS.get(
                                    failure_code, failure_code
                                )
                            lead.raw_profile_data = profile_meta
                            flag_modified(lead, "raw_profile_data")

                            # Distinguish permanent blocks from temporary failures
                            is_permanent_block = failure_code in (
                                "platform_messaging_blocked",
                            )
                            is_temporary_failure = failure_code in (
                                "message_button_not_found",
                                "message_input_not_found",
                            )

                            if is_permanent_block:
                                # Facebook explicitly says can't message — blacklist
                                logger.info(
                                    "Campaign %d: [%s] BLACKLIST — %s，永久跳过",
                                    campaign_id, target_name, failure_code,
                                )
                                lead.status = LeadStatus.blacklisted
                                await session.commit()
                                continue

                            if is_temporary_failure:
                                # Button/input not found — may be page load issue, mark as failed (retryable)
                                logger.info(
                                    "Campaign %d: [%s] FAILED (retryable) — %s",
                                    campaign_id, target_name, failure_code,
                                )
                                lead.status = LeadStatus.failed
                                await session.commit()
                                continue

                            if is_platform_restriction:
                                # Account-level block — pause campaign
                                logger.error(
                                    "Campaign %d: PLATFORM RESTRICTION for %s (code=%s) — pausing campaign",
                                    campaign_id, target_name, failure_code,
                                )
                                lead.status = LeadStatus.blacklisted
                                campaign.status = CampaignStatus.paused
                                await session.commit()
                                break

                            # Check if send failure is due to login expiry
                            login_still_ok = await _verify_facebook_login(adapter)
                            if not login_still_ok:
                                logger.error(
                                    "Campaign %d: Facebook login expired mid-campaign! Pausing.",
                                    campaign_id,
                                )
                                profile_meta2 = lead.raw_profile_data or {}
                                if isinstance(profile_meta2, dict):
                                    profile_meta2["failure_code"] = "login_expired"
                                    profile_meta2["failure_step"] = "send_message"
                                    profile_meta2["failure_reason"] = "Facebook 登录已过期"
                                lead.raw_profile_data = profile_meta2
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
                        flag_modified(lead, "raw_profile_data")
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
            _campaign_progress.pop(campaign_id, None)
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
            _campaign_progress.pop(campaign_id, None)
            campaign.status = CampaignStatus.failed
            await session.commit()

        finally:
            await adapter.close()
