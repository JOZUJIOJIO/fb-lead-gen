"""Unified AI calling layer supporting multiple providers."""

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_openai_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _build_anthropic_headers(api_key: str) -> dict:
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }


def _persona_to_system_prompt(persona: dict) -> str:
    """Convert a persona dict into a coherent system prompt in Chinese."""
    if persona.get("system_prompt"):
        return persona["system_prompt"]

    parts: list[str] = []
    parts.append("你是一位专业的社交媒体销售代表，请严格按照以下人设进行对话。")

    if persona.get("salesperson_name"):
        parts.append(f"你的名字是{persona['salesperson_name']}。")
    if persona.get("salesperson_title"):
        parts.append(f"你的职位是{persona['salesperson_title']}。")
    if persona.get("company_name"):
        parts.append(f"你所在的公司是{persona['company_name']}。")
    if persona.get("company_description"):
        parts.append(f"公司简介：{persona['company_description']}")
    if persona.get("products"):
        products = persona["products"]
        if isinstance(products, list):
            parts.append(f"你负责的产品/服务：{'、'.join(str(p) for p in products)}")
        elif isinstance(products, dict):
            parts.append(f"你负责的产品/服务：{json.dumps(products, ensure_ascii=False)}")
    if persona.get("tone"):
        parts.append(f"说话风格：{persona['tone']}。")
    if persona.get("greeting_rules"):
        rules = persona["greeting_rules"]
        if isinstance(rules, list):
            parts.append("打招呼规则：" + "；".join(str(r) for r in rules))
        elif isinstance(rules, dict):
            parts.append(f"打招呼规则：{json.dumps(rules, ensure_ascii=False)}")
    if persona.get("conversation_rules"):
        rules = persona["conversation_rules"]
        if isinstance(rules, list):
            parts.append("对话规则：" + "；".join(str(r) for r in rules))
        elif isinstance(rules, dict):
            parts.append(f"对话规则：{json.dumps(rules, ensure_ascii=False)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Provider-specific call functions
# ---------------------------------------------------------------------------

async def _call_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call any OpenAI-compatible API (OpenAI, Kimi, etc.)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_openai_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _call_openai_compatible_multi(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
) -> str:
    """Call OpenAI-compatible API with a full messages list."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_openai_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _call_anthropic(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_anthropic_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


async def _call_anthropic_multi(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
) -> str:
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_anthropic_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Router: pick the right provider
# ---------------------------------------------------------------------------

def _get_provider_config() -> tuple[str, str, str]:
    """Returns (provider, base_url, api_key) based on settings."""
    provider = settings.AI_PROVIDER.lower()
    if provider == "kimi":
        return "kimi", "https://api.moonshot.cn/v1", settings.KIMI_API_KEY or ""
    elif provider == "anthropic":
        return "anthropic", "", settings.ANTHROPIC_API_KEY or ""
    elif provider == "openrouter":
        return "openrouter", "https://openrouter.ai/api/v1", settings.OPENROUTER_API_KEY or ""
    else:
        # openai or any openai-compatible
        base = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        return "openai", base, settings.OPENAI_API_KEY or ""


def _default_model(provider: str) -> str:
    if provider == "anthropic":
        return "claude-sonnet-4-20250514"
    elif provider == "kimi":
        return "moonshot-v1-8k"
    elif provider == "openrouter":
        return "openai/gpt-5.4"
    return "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_greeting(profile_data: dict, persona: dict) -> str:
    """生成个性化的首次打招呼消息。

    Args:
        profile_data: 目标用户的资料 (name, bio, industry, interests, recent_topics).
        persona: 人设配置，字段对应 Persona 模型。
    """
    system_prompt = _persona_to_system_prompt(persona)

    user_prompt_parts = [
        "请根据以下目标用户信息，生成一条自然、个性化的首次打招呼私信。",
        "要求：不超过150字，语气真诚自然，不要过于推销，找到与对方的共同话题或切入点。",
        "",
        f"目标用户姓名：{profile_data.get('name', '未知')}",
    ]
    if profile_data.get("bio"):
        user_prompt_parts.append(f"个人简介：{profile_data['bio']}")
    if profile_data.get("industry"):
        user_prompt_parts.append(f"行业：{profile_data['industry']}")
    if profile_data.get("interests"):
        interests = profile_data["interests"]
        if isinstance(interests, list):
            user_prompt_parts.append(f"兴趣爱好：{'、'.join(interests)}")
        else:
            user_prompt_parts.append(f"兴趣爱好：{interests}")
    if profile_data.get("recent_topics"):
        topics = profile_data["recent_topics"]
        if isinstance(topics, list):
            user_prompt_parts.append(f"最近话题：{'、'.join(topics)}")
        else:
            user_prompt_parts.append(f"最近话题：{topics}")
    if profile_data.get("work"):
        user_prompt_parts.append(f"工作经历：{profile_data['work']}")
    if profile_data.get("education"):
        user_prompt_parts.append(f"教育背景：{profile_data['education']}")

    user_prompt = "\n".join(user_prompt_parts)

    provider, base_url, api_key = _get_provider_config()
    model = _default_model(provider)

    logger.info("generate_greeting: provider=%s, model=%s, target=%s", provider, model, profile_data.get("name"))

    if provider == "anthropic":
        return await _call_anthropic(api_key, model, system_prompt, user_prompt)
    else:
        return await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)


async def generate_reply(
    conversation_history: list,
    persona: dict,
    lead_profile: dict | None = None,
    current_round: int = 1,
    max_rounds: int = 10,
) -> str:
    """根据对话上下文生成回复，渐进式引导对方添加私域联系方式。

    Args:
        conversation_history: 消息列表，每条为 {"role": "user"|"assistant", "content": "..."}.
        persona: 人设配置（含 whatsapp_id / telegram_id）。
        lead_profile: 目标用户资料（name, bio, industry 等）。
        current_round: 当前回复轮次（1-based）。
        max_rounds: 最大回复轮次。
    """
    system_prompt = _persona_to_system_prompt(persona)

    # Build private-domain contact info
    contacts = []
    if persona.get("whatsapp_id"):
        contacts.append(f"WhatsApp: {persona['whatsapp_id']}")
    if persona.get("telegram_id"):
        contacts.append(f"Telegram: {persona['telegram_id']}")
    contact_str = "、".join(contacts) if contacts else ""

    # Progressive conversion strategy
    system_prompt += "\n\n## 回复规则\n"
    system_prompt += "请根据以上人设和对话历史生成一条回复。保持对话自然流畅，不要生硬推销。\n"
    system_prompt += f"当前是第 {current_round}/{max_rounds} 轮对话。\n\n"

    if contact_str:
        system_prompt += f"""## 私域引导策略
你的私域联系方式：{contact_str}

核心原则：用最少的轮次自然引导对方添加你的 WhatsApp 或 Telegram。

- 如果对方已经表现出兴趣（问价格、问合作、问详情），立刻给出联系方式，不要拖延
- 如果对方还在闲聊或表达好奇，继续建立关系，找合适时机自然带出联系方式
- 不要生硬地说"加我微信/WhatsApp"，要给出一个让对方想加你的理由（发资料、深入聊、分享案例等）
- 第 {max_rounds} 轮是最后一次机会，友好地留下联系方式

示例引导话术：
- "这个我之前整理过一份案例集，WhatsApp 上发你更方便：{contacts[0] if contacts else ''}"
- "细节在 Facebook 上聊不太方便，我们可以移步 Telegram 详聊"
- "我把产品手册发你，方便加个 WhatsApp 吗？"
"""

    if lead_profile:
        profile_parts = []
        if lead_profile.get("name"):
            profile_parts.append(f"姓名：{lead_profile['name']}")
        if lead_profile.get("bio"):
            profile_parts.append(f"简介：{lead_profile['bio'][:200]}")
        if lead_profile.get("industry"):
            profile_parts.append(f"行业：{lead_profile['industry']}")
        if lead_profile.get("work"):
            work = lead_profile["work"]
            if isinstance(work, str):
                profile_parts.append(f"工作：{work[:100]}")
        if profile_parts:
            system_prompt += "\n## 对方资料\n" + "\n".join(profile_parts) + "\n"

    system_prompt += "\n请只输出回复内容，不要输出任何解释或前缀。控制在 200 字以内。"

    provider, base_url, api_key = _get_provider_config()
    model = _default_model(provider)

    logger.info("generate_reply: provider=%s, model=%s, history_len=%d", provider, model, len(conversation_history))

    if provider == "anthropic":
        # Anthropic requires alternating user/assistant messages
        messages = []
        for msg in conversation_history:
            content = msg.get("content", "")
            if not content:
                continue
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                role = "user"
            messages.append({"role": role, "content": content})
        if not messages:
            messages = [{"role": "user", "content": "你好"}]
        return await _call_anthropic_multi(api_key, model, system_prompt, messages)
    else:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            content = msg.get("content", "")
            if not content:
                continue
            role = msg.get("role", "user")
            if role not in ("user", "assistant", "system"):
                role = "user"
            messages.append({"role": role, "content": content})
        return await _call_openai_compatible_multi(base_url, api_key, model, messages)


async def analyze_profile(raw_html: str) -> dict:
    """从个人资料页面 HTML 中提取结构化信息。

    Returns:
        dict with keys: name, bio, industry, interests, recent_topics
    """
    system_prompt = (
        "你是一个社交媒体资料分析助手。请从提供的 HTML 内容中提取用户的结构化信息。"
        "只返回 JSON 格式，不要附加任何解释文字。"
    )

    # Truncate HTML to avoid token limits (keep first ~8000 chars)
    truncated = raw_html[:8000] if len(raw_html) > 8000 else raw_html

    user_prompt = (
        "请从以下 HTML 中提取用户资料信息，返回 JSON 格式，包含以下字段：\n"
        '- name: 用户名\n'
        '- bio: 个人简介\n'
        '- industry: 所在行业\n'
        '- interests: 兴趣爱好（列表）\n'
        '- recent_topics: 最近讨论的话题（列表）\n'
        '- work: 工作经历\n'
        '- education: 教育背景\n'
        '- location: 所在地\n\n'
        f"HTML 内容：\n{truncated}"
    )

    provider, base_url, api_key = _get_provider_config()
    model = _default_model(provider)

    logger.info("analyze_profile: provider=%s, model=%s, html_len=%d", provider, model, len(raw_html))

    if provider == "anthropic":
        result_text = await _call_anthropic(api_key, model, system_prompt, user_prompt)
    else:
        result_text = await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)

    # Parse JSON from response (handle markdown code blocks)
    cleaned = result_text.strip()
    if cleaned.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("AI returned non-JSON for analyze_profile, returning raw text")
        return {
            "name": "",
            "bio": cleaned,
            "industry": "",
            "interests": [],
            "recent_topics": [],
        }
