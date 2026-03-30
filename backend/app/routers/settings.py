"""Settings router — runtime configuration management."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.models import User
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

COOKIES_FILE = Path("/tmp/leadflow-browser/facebook_cookies.json")

router = APIRouter()


class SettingsResponse(BaseModel):
    ai_provider: str
    openai_api_key_set: bool
    openai_base_url: Optional[str]
    anthropic_api_key_set: bool
    kimi_api_key_set: bool
    openrouter_api_key_set: bool
    proxy_server: Optional[str]
    send_interval_min: int
    send_interval_max: int
    max_daily_messages: int


class SettingsUpdate(BaseModel):
    ai_provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    proxy_server: Optional[str] = None
    send_interval_min: Optional[int] = None
    send_interval_max: Optional[int] = None
    max_daily_messages: Optional[int] = None


def _env_file_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / ".env"


@router.get("/", response_model=SettingsResponse)
async def get_settings(user: User = Depends(get_current_user)):
    return SettingsResponse(
        ai_provider=settings.AI_PROVIDER,
        openai_api_key_set=bool(settings.OPENAI_API_KEY),
        openai_base_url=settings.OPENAI_BASE_URL,
        anthropic_api_key_set=bool(settings.ANTHROPIC_API_KEY),
        kimi_api_key_set=bool(settings.KIMI_API_KEY),
        openrouter_api_key_set=bool(settings.OPENROUTER_API_KEY),
        proxy_server=settings.PROXY_SERVER,
        send_interval_min=settings.SEND_INTERVAL_MIN,
        send_interval_max=settings.SEND_INTERVAL_MAX,
        max_daily_messages=settings.MAX_DAILY_MESSAGES,
    )


@router.patch("/")
async def update_settings(
    body: SettingsUpdate,
    user: User = Depends(get_current_user),
):
    """Update settings in memory and persist to .env file."""
    updates: dict[str, str] = {}

    if body.ai_provider is not None:
        settings.AI_PROVIDER = body.ai_provider
        updates["AI_PROVIDER"] = body.ai_provider
    if body.openai_api_key is not None:
        settings.OPENAI_API_KEY = body.openai_api_key
        updates["OPENAI_API_KEY"] = body.openai_api_key
    if body.openai_base_url is not None:
        settings.OPENAI_BASE_URL = body.openai_base_url
        updates["OPENAI_BASE_URL"] = body.openai_base_url
    if body.anthropic_api_key is not None:
        settings.ANTHROPIC_API_KEY = body.anthropic_api_key
        updates["ANTHROPIC_API_KEY"] = body.anthropic_api_key
    if body.kimi_api_key is not None:
        settings.KIMI_API_KEY = body.kimi_api_key
        updates["KIMI_API_KEY"] = body.kimi_api_key
    if body.openrouter_api_key is not None:
        settings.OPENROUTER_API_KEY = body.openrouter_api_key
        updates["OPENROUTER_API_KEY"] = body.openrouter_api_key
    if body.proxy_server is not None:
        settings.PROXY_SERVER = body.proxy_server
        updates["PROXY_SERVER"] = body.proxy_server
    if body.send_interval_min is not None:
        settings.SEND_INTERVAL_MIN = body.send_interval_min
        updates["SEND_INTERVAL_MIN"] = str(body.send_interval_min)
    if body.send_interval_max is not None:
        settings.SEND_INTERVAL_MAX = body.send_interval_max
        updates["SEND_INTERVAL_MAX"] = str(body.send_interval_max)
    if body.max_daily_messages is not None:
        settings.MAX_DAILY_MESSAGES = body.max_daily_messages
        updates["MAX_DAILY_MESSAGES"] = str(body.max_daily_messages)

    # Persist to .env
    if updates:
        _persist_env(updates)

    return {"message": "设置已更新", "updated_keys": list(updates.keys())}


class CookiesImport(BaseModel):
    cookies: list[dict]


@router.post("/cookies")
async def import_cookies(
    body: CookiesImport,
    user: User = Depends(get_current_user),
):
    """Import browser cookies (from Cookie-Editor extension export).

    Saves cookies to file, then injects them into the Patchright browser context.
    """
    if not body.cookies:
        return {"message": "Cookies 列表为空", "success": False}

    # Ensure directory exists
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Convert Cookie-Editor format to Playwright format
    pw_cookies = []
    for c in body.cookies:
        cookie = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
        }
        if c.get("expirationDate"):
            cookie["expires"] = c["expirationDate"]
        if c.get("secure") is not None:
            cookie["secure"] = c["secure"]
        if c.get("httpOnly") is not None:
            cookie["httpOnly"] = c["httpOnly"]
        if c.get("sameSite"):
            ss = c["sameSite"].lower()
            if ss in ("strict", "lax", "none"):
                cookie["sameSite"] = ss.capitalize() if ss != "none" else "None"
        pw_cookies.append(cookie)

    # Save to file
    COOKIES_FILE.write_text(json.dumps(pw_cookies, ensure_ascii=False, indent=2))

    fb_count = sum(1 for c in pw_cookies if ".facebook.com" in c.get("domain", ""))

    # Cookie file saved — browser will load it on next adapter.initialize()
    # No need to inject into a running browser here; that caused event loop conflicts.
    return {
        "message": f"已导入 {len(pw_cookies)} 个 Cookies（其中 Facebook 相关 {fb_count} 个）。下次启动任务时将自动加载。",
        "success": True,
        "total": len(pw_cookies),
        "facebook_count": fb_count,
    }


@router.get("/cookies/status")
async def cookies_status(user: User = Depends(get_current_user)):
    """Check if Facebook cookies have been imported."""
    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text())
        fb_count = sum(1 for c in cookies if ".facebook.com" in c.get("domain", ""))
        return {"imported": True, "total": len(cookies), "facebook_count": fb_count}
    return {"imported": False, "total": 0, "facebook_count": 0}


def _persist_env(updates: dict[str, str]):
    """Merge updates into the .env file."""
    env_path = _env_file_path()
    lines: list[str] = []

    if env_path.exists():
        lines = env_path.read_text().splitlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Add any keys not yet in file
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n")
