"""Campaign orchestrator — runs the full search-analyze-message pipeline."""

import asyncio
import logging
import random

from sqlalchemy import select
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


async def _refresh_campaign_status(session: AsyncSession, campaign_id: int) -> CampaignStatus:
    """Re-read the campaign status from DB (to detect pause/stop signals)."""
    result = await session.execute(
        select(Campaign.status).where(Campaign.id == campaign_id)
    )
    row = result.scalar_one_or_none()
    return row or CampaignStatus.failed


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_campaign(campaign_id: int) -> None:  # noqa: C901
    """Execute a full campaign: search -> analyze -> message.

    This is designed to be launched as a background asyncio task.
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

        # Eagerly load the persona relationship
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

        # 2. Initialize adapter
        adapter = FacebookAdapter()
        try:
            await adapter.initialize()
        except Exception as e:
            logger.error("Campaign %d: failed to initialize adapter: %s", campaign_id, e)
            campaign.status = CampaignStatus.failed
            await session.commit()
            return

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
            campaign.progress_current = 0
            await session.commit()

            # 4. Process each target
            for idx, target in enumerate(targets):
                # Check if campaign was paused or stopped
                current_status = await _refresh_campaign_status(session, campaign_id)
                if current_status in (CampaignStatus.paused, CampaignStatus.failed):
                    logger.info("Campaign %d: stopped (status=%s)", campaign_id, current_status.value)
                    break

                profile_url = target.get("profile_url", "")
                target_name = target.get("name", "unknown")
                logger.info(
                    "Campaign %d: processing %d/%d — %s",
                    campaign_id, idx + 1, len(targets), target_name,
                )

                # 4a. Save as Lead (status=found)
                lead = Lead(
                    campaign_id=campaign_id,
                    platform=PlatformEnum.facebook,
                    platform_user_id=target.get("platform_user_id", ""),
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

                    # Merge adapter data with AI analysis
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
                        await session.commit()
                        continue

                    # 4e. Send message
                    success = await adapter.send_message(profile_url, greeting)

                    if success:
                        lead.status = LeadStatus.messaged
                        # Record the outbound message
                        msg = Message(
                            lead_id=lead.id,
                            direction=MessageDirection.outbound,
                            content=greeting,
                            ai_generated=True,
                        )
                        session.add(msg)
                    else:
                        lead.status = LeadStatus.failed

                    await session.commit()

                except Exception as e:
                    logger.error(
                        "Campaign %d: error processing lead %s: %s",
                        campaign_id, target_name, e,
                    )
                    lead.status = LeadStatus.failed
                    await session.commit()

                # 4f. Update progress
                campaign.progress_current = idx + 1
                await session.commit()

                # 4g. Wait random interval before next target
                if idx < len(targets) - 1:
                    wait_secs = random.randint(settings.SEND_INTERVAL_MIN, settings.SEND_INTERVAL_MAX)
                    logger.info("Campaign %d: waiting %ds before next target", campaign_id, wait_secs)
                    await asyncio.sleep(wait_secs)

            # 5. Mark campaign as completed (unless it was paused)
            final_status = await _refresh_campaign_status(session, campaign_id)
            if final_status == CampaignStatus.running:
                campaign.status = CampaignStatus.completed
                await session.commit()

            logger.info("Campaign %d: finished (status=%s)", campaign_id, campaign.status.value)

        except Exception as e:
            logger.error("Campaign %d: unhandled error: %s", campaign_id, e)
            campaign.status = CampaignStatus.failed
            await session.commit()

        finally:
            await adapter.close()
