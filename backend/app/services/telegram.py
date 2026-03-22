"""Telegram Bot API integration for lead messaging."""

import logging
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def generate_telegram_link(username: str, message: str = "") -> str:
    """Generate a Telegram direct message link.

    Works without Bot API — opens a chat with the user in Telegram.
    """
    clean_username = username.strip().lstrip("@")
    if message:
        encoded = quote(message)
        return f"https://t.me/{clean_username}?text={encoded}"
    return f"https://t.me/{clean_username}"


def send_telegram_message(chat_id: str, message_text: str) -> dict:
    """Send a message via Telegram Bot API.

    Requires:
    - TELEGRAM_BOT_TOKEN configured in .env
    - The user must have started a conversation with the bot first
    """
    if not settings.telegram_bot_token:
        raise ValueError(
            "Telegram Bot API not configured. Set TELEGRAM_BOT_TOKEN in .env"
        )

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=payload)
        if response.status_code != 200:
            logger.error(f"Telegram API error: {response.status_code} {response.text}")
            raise Exception(f"Telegram API error: {response.status_code}")
        return response.json()


def get_bot_info() -> dict:
    """Get bot information to verify token is valid."""
    if not settings.telegram_bot_token:
        raise ValueError("Telegram Bot API not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe"

    with httpx.Client(timeout=10) as client:
        response = client.get(url)
        if response.status_code != 200:
            raise Exception(f"Invalid Telegram bot token: {response.status_code}")
        return response.json().get("result", {})
