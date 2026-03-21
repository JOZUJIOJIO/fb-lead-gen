import logging
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPT_OUT_TEXT = "\n\n---\nReply STOP to opt out."


def generate_click_to_chat_link(phone: str, message: str) -> str:
    """Generate a WhatsApp Click-to-Chat link with pre-filled message."""
    clean_phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    full_message = message + OPT_OUT_TEXT
    encoded = quote(full_message)
    return f"https://wa.me/{clean_phone}?text={encoded}"


def send_template_message(phone: str, message_text: str) -> dict:
    """Send a message via WhatsApp Business Cloud API.

    Requires:
    - WhatsApp Business API access token
    - Approved message template
    - User must have opted in (initiated conversation first)
    """
    if not settings.whatsapp_business_token or not settings.whatsapp_phone_number_id:
        raise ValueError(
            "WhatsApp Business API not configured. "
            "Set WHATSAPP_BUSINESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID."
        )

    clean_phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "text",
        "text": {"body": message_text + OPT_OUT_TEXT},
    }

    headers = {
        "Authorization": f"Bearer {settings.whatsapp_business_token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"WhatsApp API error: {response.status_code} {response.text}")
            raise Exception(f"WhatsApp API error: {response.status_code}")
        return response.json()
