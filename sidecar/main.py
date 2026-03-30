"""LeadFlow sidecar entry point — JSON-RPC 2.0 server over stdin/stdout."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from db import Database
from jsonrpc import JsonRpcServer
from services.ai_service import AIConfig

# ---------------------------------------------------------------------------
# Logging — all output goes to stderr; stdout is reserved for JSON-RPC traffic
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("leadflow.sidecar")

# ---------------------------------------------------------------------------
# Module-level singletons (overridable in tests)
# ---------------------------------------------------------------------------
server = JsonRpcServer()
_db: Optional[Database] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> Optional[dict]:
    """Convert an aiosqlite.Row to a plain dict, or return None."""
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows) -> list:
    """Convert a list of aiosqlite.Row objects to a list of dicts."""
    return [dict(r) for r in rows]


async def _get_ai_config() -> AIConfig:
    """Read AI provider settings from the database and return an AIConfig."""
    provider = await _db.get_setting("ai_provider") or "openai"
    api_key = await _db.get_setting("api_key") or ""
    base_url = await _db.get_setting("base_url") or None
    return AIConfig(provider=provider, api_key=api_key, base_url=base_url)


# ---------------------------------------------------------------------------
# System methods
# ---------------------------------------------------------------------------

@server.method("ping")
async def ping() -> str:
    logger.debug("ping received")
    return "pong"


@server.method("get_status")
async def get_status() -> dict:
    logger.debug("get_status received")
    messages_sent_today = await _db.count_messages_today()
    return {
        "version": "0.1.0",
        "db": "connected",
        "messages_sent_today": messages_sent_today,
    }


# ---------------------------------------------------------------------------
# Campaign methods
# ---------------------------------------------------------------------------

@server.method("create_campaign")
async def create_campaign(
    platform: str,
    search_keywords: str = None,
    search_region: str = None,
    search_industry: str = None,
    persona_id: int = None,
    send_limit: int = 50,
) -> dict:
    campaign_id = await _db.create_campaign(
        platform=platform,
        search_keywords=search_keywords,
        search_region=search_region,
        search_industry=search_industry,
        persona_id=persona_id,
        send_limit=send_limit,
    )
    row = await _db.get_campaign(campaign_id)
    return _row_to_dict(row)


@server.method("list_campaigns")
async def list_campaigns(status: str = None) -> list:
    rows = await _db.list_campaigns(status=status)
    return _rows_to_list(rows)


@server.method("get_campaign")
async def get_campaign(campaign_id: int) -> Optional[dict]:
    row = await _db.get_campaign(campaign_id)
    if row is None:
        return None
    campaign = _row_to_dict(row)
    # Include the leads list for this campaign
    lead_rows = await _db.list_leads(campaign_id=campaign_id)
    campaign["leads"] = _rows_to_list(lead_rows)
    return campaign


# ---------------------------------------------------------------------------
# Lead methods
# ---------------------------------------------------------------------------

@server.method("list_leads")
async def list_leads(
    campaign_id: int = None,
    status: str = None,
    intent: float = None,
) -> list:
    rows = await _db.list_leads(campaign_id=campaign_id, status=status, intent=intent)
    return _rows_to_list(rows)


@server.method("get_lead")
async def get_lead(lead_id: int) -> Optional[dict]:
    row = await _db.get_lead(lead_id)
    return _row_to_dict(row)


@server.method("get_conversation")
async def get_conversation(lead_id: int) -> list:
    rows = await _db.get_conversation(lead_id)
    return _rows_to_list(rows)


# ---------------------------------------------------------------------------
# Persona methods
# ---------------------------------------------------------------------------

@server.method("list_personas")
async def list_personas() -> list:
    rows = await _db.list_personas()
    return _rows_to_list(rows)


@server.method("get_persona")
async def get_persona(persona_id: int) -> Optional[dict]:
    row = await _db.get_persona(persona_id)
    return _row_to_dict(row)


@server.method("create_persona")
async def create_persona(
    name: str,
    description: str = None,
    company_name: str = None,
    company_description: str = None,
    products: str = None,
    salesperson_name: str = None,
    salesperson_title: str = None,
    tone: str = None,
    greeting_rules: str = None,
    conversation_rules: str = None,
    transfer_conditions: str = None,
    system_prompt: str = None,
) -> dict:
    # `description` is a friendlier alias for `company_description`
    effective_company_description = company_description or description
    persona_id = await _db.create_persona(
        name=name,
        company_name=company_name,
        company_description=effective_company_description,
        products=products,
        salesperson_name=salesperson_name,
        salesperson_title=salesperson_title,
        tone=tone,
        greeting_rules=greeting_rules,
        conversation_rules=conversation_rules,
        transfer_conditions=transfer_conditions,
        system_prompt=system_prompt,
    )
    row = await _db.get_persona(persona_id)
    return _row_to_dict(row)


@server.method("update_persona")
async def update_persona(persona_id: int, **fields) -> Optional[dict]:
    await _db.update_persona(persona_id, **fields)
    row = await _db.get_persona(persona_id)
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Settings methods
# ---------------------------------------------------------------------------

@server.method("get_setting")
async def get_setting(key: str) -> Optional[str]:
    return await _db.get_setting(key)


@server.method("set_setting")
async def set_setting(key: str, value: str) -> dict:
    await _db.set_setting(key, value)
    return {"ok": True, "key": key}


# ---------------------------------------------------------------------------
# Campaign control
# ---------------------------------------------------------------------------

@server.method("start_campaign")
async def rpc_start_campaign(campaign_id: int) -> dict:
    from services.campaign_runner import start_campaign
    ai_config = await _get_ai_config()
    message = await start_campaign(campaign_id, _db, ai_config)
    row = await _db.get_campaign(campaign_id)
    result = _row_to_dict(row) or {}
    result["message"] = message
    return result


@server.method("pause_campaign")
async def rpc_pause_campaign(campaign_id: int) -> dict:
    from services.campaign_runner import pause_campaign
    message = await pause_campaign(campaign_id, _db)
    row = await _db.get_campaign(campaign_id)
    result = _row_to_dict(row) or {}
    result["message"] = message
    return result


@server.method("stop_campaign")
async def rpc_stop_campaign(campaign_id: int) -> dict:
    from services.campaign_runner import stop_campaign
    message = await stop_campaign(campaign_id, _db)
    row = await _db.get_campaign(campaign_id)
    result = _row_to_dict(row) or {}
    result["message"] = message
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main() -> None:
    global _db

    DATA_DIR = Path.home() / "Library" / "Application Support" / "LeadFlow"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DATA_DIR / "leadflow.db"

    logger.info("LeadFlow sidecar starting — db=%s", DB_PATH)
    _db = Database(str(DB_PATH))
    await _db.initialize()
    logger.info("Database initialized")

    try:
        await server.run()
    finally:
        await _db.close()
        logger.info("LeadFlow sidecar stopped")


if __name__ == "__main__":
    asyncio.run(_main())
