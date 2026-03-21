import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded Anthropic client
_anthropic_client = None


def _call_kimi(prompt: str, max_tokens: int = 500) -> str:
    """Call Kimi 2.5 API (OpenAI-compatible format)."""
    url = f"{settings.kimi_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.kimi_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.kimi_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    with httpx.Client(timeout=60) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


def _call_anthropic(prompt: str, max_tokens: int = 500) -> str:
    """Call Anthropic Claude API."""
    global _anthropic_client
    import anthropic

    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = _anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _call_ai(prompt: str, max_tokens: int = 500) -> str:
    """Route to configured AI provider."""
    provider = settings.ai_provider.lower()

    if provider == "kimi" and settings.kimi_api_key:
        return _call_kimi(prompt, max_tokens)
    elif provider == "anthropic" and settings.anthropic_api_key:
        return _call_anthropic(prompt, max_tokens)
    elif settings.kimi_api_key:
        return _call_kimi(prompt, max_tokens)
    elif settings.anthropic_api_key:
        return _call_anthropic(prompt, max_tokens)
    else:
        raise ValueError("No AI API key configured. Set KIMI_API_KEY or ANTHROPIC_API_KEY.")


def _parse_json_response(text: str) -> dict:
    """Extract JSON from AI response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def analyze_lead(
    name: str,
    company: str,
    profile_data: dict[str, Any],
    email: str = "",
) -> dict:
    """Analyze a lead using AI and return score, analysis, and detected language."""
    if not settings.kimi_api_key and not settings.anthropic_api_key:
        return {
            "score": 50,
            "analysis": "AI analysis unavailable — no API key configured. Set KIMI_API_KEY or ANTHROPIC_API_KEY.",
            "language": "en",
        }

    profile_str = json.dumps(profile_data, ensure_ascii=False) if profile_data else "No additional data"

    prompt = f"""Analyze this potential B2B buyer lead for a Chinese export/foreign trade company.

Lead information:
- Name: {name}
- Company: {company}
- Email: {email}
- Additional profile data: {profile_str}

Please evaluate this lead and respond in JSON format with these fields:
1. "score": An intent score from 0-100 indicating how likely this person is a qualified B2B buyer.
   - 80-100: High priority - clear B2B buyer signals (procurement role, relevant industry, importing company)
   - 60-79: Medium priority - some buying signals present
   - 40-59: Low priority - limited signals but possible buyer
   - 0-39: Not a likely buyer
2. "analysis": A 2-3 sentence analysis explaining your scoring rationale. Mention specific signals you identified.
3. "language": The detected primary language of this person (ISO 639-1 code, e.g., "en", "es", "fr", "ar", "pt").
   Detect from their name, company name, and any profile data. Default to "en" if uncertain.

Scoring criteria:
- Company relevance to B2B importing/wholesale/distribution
- Role seniority (decision-maker vs. junior)
- Industry alignment with typical Chinese export goods
- Geographic market (emerging markets often have stronger demand)
- Any engagement signals (comments on trade posts, etc.)

Respond ONLY with valid JSON, no other text."""

    try:
        response_text = _call_ai(prompt)
        result = _parse_json_response(response_text)
        return {
            "score": max(0, min(100, float(result.get("score", 50)))),
            "analysis": result.get("analysis", ""),
            "language": result.get("language", "en"),
        }
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {
            "score": 50,
            "analysis": f"AI analysis error: {str(e)}",
            "language": "en",
        }


def generate_message(
    lead_name: str,
    lead_company: str,
    lead_data: dict[str, Any],
    template_body: str,
    language: str = "en",
) -> str:
    """Generate a personalized outreach message using AI."""
    if not settings.kimi_api_key and not settings.anthropic_api_key:
        return template_body.replace("{{name}}", lead_name).replace("{{company}}", lead_company)

    profile_str = json.dumps(lead_data, ensure_ascii=False) if lead_data else "No additional data"

    prompt = f"""Generate a personalized WhatsApp outreach message for a B2B lead.

Context: A Chinese export company wants to connect with this potential buyer via WhatsApp.

Lead information:
- Name: {lead_name}
- Company: {lead_company}
- Additional data: {profile_str}

Message template to personalize:
{template_body}

Requirements:
1. Write the message in {language} language
2. Keep it professional but warm and conversational (WhatsApp style, not email style)
3. Personalize based on the lead's company and any available profile data
4. Include a clear reason why connecting would benefit them
5. Keep it under 200 words
6. End with a soft call-to-action (e.g., "Would you be open to a quick chat?")
7. Do NOT include any opt-out text (that will be added automatically)
8. Replace any {{{{variable}}}} placeholders with actual personalized content

Respond with ONLY the message text, no quotes or explanation."""

    try:
        return _call_ai(prompt, max_tokens=400)
    except Exception as e:
        logger.error(f"Message generation failed: {e}")
        return template_body.replace("{{name}}", lead_name).replace("{{company}}", lead_company)
