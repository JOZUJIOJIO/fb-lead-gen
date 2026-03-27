"""
LeadFlow MCP Server — OpenClaw 插件

让 OpenClaw 通过 WhatsApp 操控 LeadFlow 获客系统。
业务员在 WhatsApp 上说"帮我找东南亚做电子产品的买家"，
OpenClaw 调用这些工具完成搜索、分析、发消息的全流程。

启动方式: python server.py
OpenClaw 配置: 在 OpenClaw 的 MCP settings 中添加本服务器
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import logging

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# 优先使用 OpenCLI（复用 Chrome 登录态），连不上则回退 Playwright
import browser_agent_opencli
import browser_agent as browser_agent_playwright

_browser_backend = "auto"  # "opencli", "playwright", "auto"


def _get_browser_module():
    """根据可用性选择浏览器后端。"""
    global _browser_backend
    if _browser_backend == "playwright":
        return browser_agent_playwright
    if _browser_backend == "opencli":
        return browser_agent_opencli

    # auto: 先检查 opencli CLI 是否安装（同步，快速）
    if browser_agent_opencli._opencli_available():
        return browser_agent_opencli

    return browser_agent_playwright


def _get_FacebookBrowser():
    return _get_browser_module().FacebookBrowser


def _get_find_customers():
    return _get_browser_module().find_customers


def _get_ai_analyze_profiles():
    return _get_browser_module().ai_analyze_profiles


from conversation_engine import (
    ConversationState,
    generate_opening_message,
    generate_reply,
    get_conversation_summary,
    list_active_conversations,
    MAX_TURNS,
)

# --- 配置 ---
LEADFLOW_BASE_URL = os.environ.get("LEADFLOW_BASE_URL", "http://localhost:8000")
LEADFLOW_EMAIL = os.environ.get("LEADFLOW_EMAIL", "admin@leadflow.com")
LEADFLOW_PASSWORD = os.environ.get("LEADFLOW_PASSWORD", "admin123456")
FB_EMAIL = os.environ.get("FB_EMAIL", "")
FB_PASSWORD = os.environ.get("FB_PASSWORD", "")

# --- DM 重试配置 ---
DM_MAX_RETRIES = int(os.environ.get("DM_MAX_RETRIES", "3"))
DM_RETRY_BASE_DELAY = float(os.environ.get("DM_RETRY_BASE_DELAY", "2.0"))  # 秒

# --- WhatsApp 速率限制配置 ---
WA_RATE_LIMIT_PER_MINUTE = int(os.environ.get("WA_RATE_LIMIT_PER_MINUTE", "20"))
WA_RATE_LIMIT_PER_HOUR = int(os.environ.get("WA_RATE_LIMIT_PER_HOUR", "200"))


# ============================================================
# 工具函数：重试 & 限流
# ============================================================


async def _send_dm_with_retry(fb, profile_url: str, message: str) -> bool:
    """发送 Facebook DM，失败时指数退避重试（最多 DM_MAX_RETRIES 次）。"""
    for attempt in range(1, DM_MAX_RETRIES + 1):
        try:
            success = await fb.send_dm(profile_url, message)
            if success:
                return True
            logger.warning(f"DM 发送返回 False (第{attempt}次): {profile_url}")
        except Exception as e:
            logger.warning(f"DM 发送异常 (第{attempt}次): {e}")

        if attempt < DM_MAX_RETRIES:
            delay = DM_RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 2s, 4s, 8s...
            logger.info(f"等待 {delay:.1f}s 后重试...")
            await asyncio.sleep(delay)

    logger.error(f"DM 发送最终失败 (已重试{DM_MAX_RETRIES}次): {profile_url}")
    return False


class WhatsAppRateLimiter:
    """基于令牌桶的 WhatsApp 消息速率限制器。

    在内存中跟踪发送时间戳，按分钟和小时两个维度限流。
    适用于单进程部署；如需多进程，可替换为 Redis 实现。
    """

    def __init__(self, per_minute: int = 20, per_hour: int = 200):
        self.per_minute = per_minute
        self.per_hour = per_hour
        self._timestamps: list[float] = []

    def _cleanup(self, now: float):
        """清理超过 1 小时的记录。"""
        cutoff = now - 3600
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

    def can_send(self) -> bool:
        """检查是否可以发送。"""
        now = time.time()
        self._cleanup(now)

        # 检查每小时限额
        if len(self._timestamps) >= self.per_hour:
            return False

        # 检查每分钟限额
        one_min_ago = now - 60
        recent = sum(1 for ts in self._timestamps if ts > one_min_ago)
        if recent >= self.per_minute:
            return False

        return True

    def wait_time(self) -> float:
        """返回需要等待的秒数（0 表示可以立即发送）。"""
        now = time.time()
        self._cleanup(now)

        # 检查每小时
        if len(self._timestamps) >= self.per_hour:
            oldest_in_hour = self._timestamps[0]
            return oldest_in_hour + 3600 - now + 0.1

        # 检查每分钟
        one_min_ago = now - 60
        recent_ts = [ts for ts in self._timestamps if ts > one_min_ago]
        if len(recent_ts) >= self.per_minute:
            oldest_in_min = recent_ts[0]
            return oldest_in_min + 60 - now + 0.1

        return 0.0

    def record_send(self):
        """记录一次发送。"""
        self._timestamps.append(time.time())

    async def acquire(self):
        """等待直到可以发送，然后记录。"""
        while True:
            wait = self.wait_time()
            if wait <= 0:
                self.record_send()
                return
            logger.info(f"WhatsApp 限流: 等待 {wait:.1f}s")
            await asyncio.sleep(wait)


# 全局限流器实例
_wa_limiter = WhatsAppRateLimiter(
    per_minute=WA_RATE_LIMIT_PER_MINUTE,
    per_hour=WA_RATE_LIMIT_PER_HOUR,
)

# --- MCP Server ---
mcp = FastMCP(
    "LeadFlow AI",
    description="外贸智能获客系统 — 在 WhatsApp 中搜索客户、AI分析、生成消息、发送触达",
)

# --- HTTP Client ---
_token: str | None = None


def _get_token() -> str:
    """获取或刷新 JWT token"""
    global _token
    if _token:
        return _token
    with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=30) as client:
        resp = client.post(
            "/auth/login",
            json={"email": LEADFLOW_EMAIL, "password": LEADFLOW_PASSWORD},
        )
        resp.raise_for_status()
        _token = resp.json()["access_token"]
        return _token


def _api(method: str, path: str, **kwargs) -> Any:
    """调用 LeadFlow API"""
    global _token
    token = _get_token()
    with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=60) as client:
        resp = client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        if resp.status_code == 401:
            _token = None
            token = _get_token()
            resp = client.request(
                method,
                path,
                headers={"Authorization": f"Bearer {token}"},
                **kwargs,
            )
        resp.raise_for_status()
        return resp.json()


# ============================================================
# Tools — OpenClaw 可调用的工具
# ============================================================


@mcp.tool()
def search_leads(
    keyword: str = "",
    status: str = "",
    min_score: float = 0,
    page: int = 1,
    page_size: int = 20,
) -> str:
    """搜索客户线索。

    可按关键词（姓名/公司/邮箱）、状态和最低评分筛选。
    状态可选: new(新线索), analyzed(已分析), contacted(已联系), replied(已回复), converted(已转化)

    示例用法:
    - "帮我找做电子产品的客户" → keyword="电子产品"
    - "找评分80分以上的高质量线索" → min_score=80
    - "看看有哪些客户回复了" → status="replied"
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if keyword:
        params["search"] = keyword
    if status:
        params["status"] = status
    if min_score > 0:
        params["min_score"] = min_score
    params["sort_by"] = "score"
    params["sort_order"] = "desc"

    data = _api("GET", "/leads", params=params)
    items = data.get("items", [])
    total = data.get("total", 0)

    if not items:
        return f"没有找到匹配的线索。当前共有 {total} 条线索。"

    lines = [f"找到 {total} 条线索（显示前 {len(items)} 条）：\n"]
    for i, lead in enumerate(items, 1):
        score = lead.get("score", 0)
        score_emoji = "🔴" if score < 40 else "🟡" if score < 60 else "🟢" if score < 80 else "⭐"
        lines.append(
            f"{i}. {score_emoji} {lead['name']} | {lead.get('company', '-')} | "
            f"评分:{score:.0f} | 状态:{lead['status']} | "
            f"电话:{lead.get('phone', '-')} | ID:{lead['id']}"
        )

    return "\n".join(lines)


@mcp.tool()
def get_lead_detail(lead_id: int) -> str:
    """获取单个客户线索的详细信息，包括AI分析结果。"""
    lead = _api("GET", f"/leads/{lead_id}")
    return (
        f"📋 线索详情\n"
        f"姓名: {lead['name']}\n"
        f"公司: {lead.get('company', '-')}\n"
        f"电话: {lead.get('phone', '-')}\n"
        f"邮箱: {lead.get('email', '-')}\n"
        f"评分: {lead['score']:.0f}/100\n"
        f"状态: {lead['status']}\n"
        f"语言: {lead.get('language', '-')}\n"
        f"来源: {lead.get('source', '-')}\n"
        f"\nAI分析:\n{lead.get('ai_analysis', '尚未分析')}"
    )


@mcp.tool()
def add_lead(
    name: str,
    company: str = "",
    phone: str = "",
    email: str = "",
    language: str = "en",
) -> str:
    """手动添加一个新的客户线索。

    示例: "添加一个客户 John Smith，公司 ABC Trading，电话 +6281234567"
    """
    data = {
        "name": name,
        "company": company,
        "phone": phone,
        "email": email,
        "language": language,
    }
    lead = _api("POST", "/leads", json=data)
    return f"✅ 已添加线索: {lead['name']} (ID: {lead['id']})"


@mcp.tool()
def analyze_lead(lead_id: int) -> str:
    """用AI分析一个客户线索，评估其购买意向（0-100分）。

    分析结果包括：意向评分、分析理由、检测到的语言。
    评分 ≥60 进入触达候选池，≥80 为高优先级。
    """
    lead = _api("POST", f"/leads/{lead_id}/analyze")
    score = lead["score"]
    level = "🔴 低" if score < 40 else "🟡 中" if score < 60 else "🟢 高" if score < 80 else "⭐ 极高"
    return (
        f"🤖 AI分析完成\n"
        f"客户: {lead['name']} ({lead.get('company', '-')})\n"
        f"评分: {score:.0f}/100 ({level})\n"
        f"语言: {lead.get('language', '-')}\n"
        f"\n分析: {lead.get('ai_analysis', '-')}"
    )


@mcp.tool()
def batch_analyze_leads(lead_ids: list[int]) -> str:
    """批量AI分析多个线索。传入线索ID列表。

    示例: "分析ID为1,2,3的线索"
    """
    result = _api("POST", "/leads/batch-analyze", json={"ids": lead_ids})
    return f"✅ 批量分析完成: {result['analyzed']}/{result['total']} 个线索已分析"


@mcp.tool()
def create_template(
    name: str,
    body: str,
    language: str = "en",
) -> str:
    """创建消息模板。模板中可用 {{name}} {{company}} 等变量。

    示例: "创建一个英文模板，内容是 Hi {{name}}, I noticed {{company}} might need..."
    """
    variables = []
    import re
    for match in re.finditer(r"\{\{(\w+)\}\}", body):
        variables.append(match.group(1))

    template = _api(
        "POST",
        "/templates",
        json={
            "name": name,
            "body": body,
            "variables": variables,
            "language": language,
        },
    )
    return f"✅ 模板已创建: {template['name']} (ID: {template['id']})"


@mcp.tool()
def list_templates() -> str:
    """列出所有消息模板。"""
    templates = _api("GET", "/templates")
    if not templates:
        return "暂无模板。请先创建一个模板。"
    lines = ["📝 消息模板列表：\n"]
    for t in templates:
        lines.append(f"• [{t['id']}] {t['name']} ({t['language']}) — {t['body'][:50]}...")
    return "\n".join(lines)


@mcp.tool()
def create_campaign(
    name: str,
    template_id: int,
    min_score: int = 60,
    target_status: str = "analyzed",
) -> str:
    """创建营销活动。指定模板和目标线索筛选条件。

    示例: "创建一个活动叫'东南亚电子产品'，用模板1，只发给评分60以上的"
    """
    campaign = _api(
        "POST",
        "/campaigns",
        json={
            "name": name,
            "message_template_id": template_id,
            "target_criteria": {
                "min_score": min_score,
                "status": target_status,
            },
        },
    )
    return f"✅ 活动已创建: {campaign['name']} (ID: {campaign['id']})"


@mcp.tool()
def launch_campaign(campaign_id: int) -> str:
    """启动营销活动。系统将为符合条件的线索生成个性化消息（需人工审核后发送）。

    启动后会为每个目标线索生成AI个性化消息和WhatsApp链接。
    消息需要审核后才会发送。
    """
    result = _api("POST", f"/campaigns/{campaign_id}/launch")
    return (
        f"🚀 活动已启动！\n"
        f"目标线索: {result['total_leads']} 个\n"
        f"生成消息: {result['messages_created']} 条\n"
        f"\n消息已生成，等待审核。使用 approve_messages 审核后发送。"
    )


@mcp.tool()
def list_pending_messages(campaign_id: int = 0) -> str:
    """查看待审核的消息列表。可指定活动ID筛选。"""
    params: dict[str, Any] = {"status": "pending_approval", "page_size": 20}
    if campaign_id > 0:
        params["campaign_id"] = campaign_id

    data = _api("GET", "/messages", params=params)
    items = data.get("items", [])
    total = data.get("total", 0)

    if not items:
        return "没有待审核的消息。"

    lines = [f"📨 待审核消息 ({total} 条)：\n"]
    for msg in items:
        lines.append(
            f"• [ID:{msg['id']}] → {msg.get('lead_name', '?')} ({msg.get('lead_company', '')})\n"
            f"  内容: {msg['content'][:80]}...\n"
            f"  WhatsApp链接: {msg.get('click_to_chat_link', '-')[:60]}..."
        )
    return "\n".join(lines)


@mcp.tool()
def approve_and_send_messages(message_ids: list[int]) -> str:
    """审核并发送消息。传入消息ID列表。

    审核通过后会生成 WhatsApp Click-to-Chat 链接。
    如果客户通过 Facebook/WhatsApp 回复，你会直接在 WhatsApp 收到。
    """
    approve_result = _api("POST", "/messages/batch-approve", json={"ids": message_ids})
    send_result = _api("POST", "/messages/batch-send", json={"ids": message_ids})
    return (
        f"✅ 操作完成\n"
        f"审核通过: {approve_result['approved']} 条\n"
        f"已发送: {send_result['sent']} 条\n"
        f"失败: {send_result.get('failed', 0)} 条\n"
        f"\n客户回复将直接出现在你的 WhatsApp 中。"
    )


@mcp.tool()
def get_message_stats() -> str:
    """获取消息统计数据：总数、各状态数量、回复率。"""
    stats = _api("GET", "/messages/stats")
    total = stats.get("total", 0)
    sent = stats.get("sent", 0)
    replied = stats.get("replied", 0)
    reply_rate = f"{(replied / sent * 100):.1f}%" if sent > 0 else "0%"

    return (
        f"📊 消息统计\n"
        f"总消息: {total}\n"
        f"待审核: {stats.get('pending_approval', 0)}\n"
        f"已审核: {stats.get('approved', 0)}\n"
        f"已发送: {sent}\n"
        f"已送达: {stats.get('delivered', 0)}\n"
        f"已读: {stats.get('read', 0)}\n"
        f"已回复: {replied}\n"
        f"失败: {stats.get('failed', 0)}\n"
        f"\n回复率: {reply_rate}"
    )


@mcp.tool()
def login_facebook(email: str, password: str) -> str:
    """登录 Facebook 账号。首次使用前必须调用。

    登录成功后会保存登录状态，后续不需要再次登录。
    注意：如果有两步验证，可能需要手动处理。
    """
    async def _login():
        fb = _get_FacebookBrowser()()
        try:
            await fb.start(headless=False)  # 首次登录用有头模式，方便处理验证码
            if await fb.is_logged_in():
                return "✅ 已经登录 Facebook，无需重复登录。"
            success = await fb.login(email, password)
            if success:
                return "✅ Facebook 登录成功！登录状态已保存。"
            else:
                return "❌ 登录失败。请检查邮箱密码，或手动处理两步验证后重试。"
        finally:
            await fb.close()

    return asyncio.run(_login())


@mcp.tool()
def facebook_find_customers(
    query: str,
    search_type: str = "all",
    max_results: int = 20,
    auto_import: bool = True,
) -> str:
    """在 Facebook 上搜索潜在客户！这是核心获客工具。

    操控浏览器打开 Facebook，搜索关键词，提取潜在客户信息，
    用 AI 评估意向评分，并自动导入到 LeadFlow 系统。

    参数:
    - query: 搜索关键词，如 "electronics importer Southeast Asia"
    - search_type: 搜索类型 - "people"(搜人), "pages"(搜公司页面), "groups"(搜群组), "all"(全部)
    - max_results: 最大结果数
    - auto_import: 是否自动导入到 LeadFlow（默认是）

    示例:
    - "帮我在Facebook上找做电子产品的东南亚买家"
      → query="electronics buyer Southeast Asia", search_type="all"
    - "搜索Facebook上的LED灯具进口商"
      → query="LED lighting importer wholesale"
    - "找Facebook上和纺织品相关的群组"
      → query="textile import wholesale", search_type="groups"
    """
    async def _search():
        result = await _get_find_customers()(
            query=query,
            search_type=search_type,
            max_results=max_results,
            headless=True,
            fb_email=FB_EMAIL,
            fb_password=FB_PASSWORD,
        )

        if not result["success"]:
            return f"❌ {result['message']}"

        profiles = result["profiles"]
        groups = result["groups"]
        imported_count = 0

        # 自动导入到 LeadFlow
        if auto_import and profiles:
            for p in profiles:
                try:
                    _api(
                        "POST",
                        "/leads",
                        json={
                            "name": p.get("name", "Unknown"),
                            "company": p.get("company", ""),
                            "phone": p.get("phone", ""),
                            "email": p.get("email", ""),
                            "source": "graph_api",
                            "source_url": p.get("profile_url", ""),
                            "profile_data": {
                                "bio": p.get("bio", ""),
                                "location": p.get("location", ""),
                                "ai_reason": p.get("ai_reason", ""),
                                "search_query": query,
                            },
                            "language": p.get("language", "en"),
                        },
                    )
                    imported_count += 1
                except Exception:
                    continue

        # 构建返回消息
        lines = [f"🔍 Facebook 搜索完成: \"{query}\"\n"]

        if profiles:
            lines.append(f"👤 找到 {len(profiles)} 个潜在客户：\n")
            for i, p in enumerate(profiles[:10], 1):
                score = p.get("score", "?")
                score_emoji = "🔴" if isinstance(score, (int, float)) and score < 40 else "🟡" if isinstance(score, (int, float)) and score < 60 else "🟢" if isinstance(score, (int, float)) and score < 80 else "⭐"
                lines.append(
                    f"{i}. {score_emoji} {p['name']}"
                    + (f" | {p['company']}" if p.get("company") else "")
                    + (f" | 评分:{score}" if score != "?" else "")
                )
                if p.get("ai_reason"):
                    lines.append(f"   → {p['ai_reason']}")

            if len(profiles) > 10:
                lines.append(f"   ... 还有 {len(profiles) - 10} 个")

        if groups:
            lines.append(f"\n👥 找到 {len(groups)} 个相关群组：")
            for g in groups[:5]:
                lines.append(f"  • {g['name']}")

        if imported_count > 0:
            lines.append(f"\n✅ 已自动导入 {imported_count} 条线索到 LeadFlow。")
            lines.append("下一步: 说「分析这些客户」进行 AI 深度分析，或「准备触达消息」生成个性化消息。")

        return "\n".join(lines)

    return asyncio.run(_search())


@mcp.tool()
def facebook_explore_group(
    group_url: str,
    auto_import: bool = True,
) -> str:
    """进入一个 Facebook 群组，提取活跃成员信息。

    先用 facebook_find_customers(search_type="groups") 找到群组，
    然后用这个工具深入群组提取成员。

    示例: "进入这个LED灯具采购群，看看里面有哪些活跃买家"
    """
    async def _explore():
        fb = _get_FacebookBrowser()()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return "❌ 未登录 Facebook。请先用 login_facebook 登录。"

            members = await fb.extract_group_members(group_url, max_members=20)
            if not members:
                return "未能提取群组成员。可能需要先加入该群组。"

            # AI 分析
            members = await _get_ai_analyze_profiles()(members, f"Group: {group_url}")

            # 导入
            imported = 0
            if auto_import:
                for m in members:
                    try:
                        _api("POST", "/leads", json={
                            "name": m.get("name", "Unknown"),
                            "company": m.get("company", ""),
                            "phone": m.get("phone", ""),
                            "email": m.get("email", ""),
                            "source": "graph_api",
                            "source_url": m.get("profile_url", ""),
                            "profile_data": {"source_group": group_url},
                            "language": m.get("language", "en"),
                        })
                        imported += 1
                    except Exception:
                        continue

            lines = [f"👥 群组成员提取完成: {len(members)} 人\n"]
            for i, m in enumerate(members[:10], 1):
                score = m.get("score", "?")
                lines.append(f"{i}. {m['name']}" + (f" | 评分:{score}" if score != "?" else ""))

            if imported > 0:
                lines.append(f"\n✅ 已导入 {imported} 条线索。")

            return "\n".join(lines)
        finally:
            await fb.close()

    return asyncio.run(_explore())


@mcp.tool()
def facebook_visit_profile(profile_url: str) -> str:
    """访问一个 Facebook 用户的个人主页，提取详细信息。

    包括：工作经历、公司、位置、联系方式（如果公开的话）。
    用于深入了解某个特定的潜在客户。
    """
    async def _visit():
        fb = _get_FacebookBrowser()()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return "❌ 未登录 Facebook。请先用 login_facebook 登录。"

            info = await fb.visit_profile(profile_url)
            lines = ["📋 用户资料：\n"]
            for key, value in info.items():
                if value and key != "profile_url":
                    label = {
                        "name": "姓名", "company": "公司", "location": "位置",
                        "bio": "简介", "phone": "电话", "email": "邮箱",
                    }.get(key, key)
                    lines.append(f"  {label}: {value}")
            lines.append(f"  链接: {profile_url}")
            return "\n".join(lines)
        finally:
            await fb.close()

    return asyncio.run(_visit())


@mcp.tool()
def start_conversation(
    lead_id: int,
    profile_url: str,
    our_company: str = "",
    our_products: str = "",
) -> str:
    """主动给一个Facebook客户发私信打招呼，开始获客对话。

    这是获客的核心动作！AI会根据客户画像生成个性化的打招呼消息，
    通过Facebook Messenger发送，然后进入自动对话流程。

    在10轮对话内完成：了解需求 → 判断意向 → 引导加WhatsApp。

    示例: "给这个客户发个私信打招呼" / "开始跟ID为5的客户聊"
    """
    async def _start():
        # 获取客户信息
        try:
            lead = _api("GET", f"/leads/{lead_id}")
        except Exception:
            lead = {"name": "Customer", "company": "", "language": "en"}

        # 创建对话状态
        state = ConversationState(
            lead_id=str(lead_id),
            lead_name=lead.get("name", "Customer"),
            lead_company=lead.get("company", ""),
            lead_industry=lead.get("profile_data", {}).get("industry", ""),
            lead_language=lead.get("language", "en"),
            our_company=our_company,
            our_products=our_products,
        )

        # AI 生成打招呼消息
        opening = generate_opening_message(state)

        # 通过浏览器发送 Facebook 私信
        fb = _get_FacebookBrowser()()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return "❌ 未登录 Facebook。请先用 login_facebook 登录。"

            success = await _send_dm_with_retry(fb, profile_url, opening)
            if not success:
                return f"❌ 私信发送失败（已重试{DM_MAX_RETRIES}次）。可能对方关闭了消息功能。\n\n原本要发送的内容:\n{opening}"

            # 记录对话
            state.add_our_message(opening)
            state.stage = "cold"

            # 更新 LeadFlow 状态
            try:
                _api("PUT", f"/leads/{lead_id}", json={"status": "contacted"})
            except Exception:
                pass

            return (
                f"✅ 已给 {lead.get('name', 'Customer')} 发送私信！\n\n"
                f"📤 发送内容:\n{opening}\n\n"
                f"📊 对话状态: 第1轮/{MAX_TURNS}轮 | 阶段: ❄️ 冷启动\n"
                f"⏳ 等待客户回复。回复后用 check_replies 查看并继续对话。"
            )
        finally:
            await fb.close()

    return asyncio.run(_start())


@mcp.tool()
def check_replies(lead_id: int, profile_url: str) -> str:
    """检查客户是否回复了私信，如果有回复则AI自动生成下一轮回复。

    这个工具会：
    1. 打开Facebook查看最新消息
    2. 如果客户回复了，AI分析意向并生成回复
    3. 自动发送回复
    4. 更新对话状态和意向评分

    定期调用此工具来推进对话（建议每5-10分钟检查一次）。
    """
    async def _check():
        state = ConversationState.load(str(lead_id))
        if not state:
            return f"❌ 没有与客户 {lead_id} 的对话记录。请先用 start_conversation 开始对话。"

        if state.turn_count >= MAX_TURNS:
            return (
                f"⚠️ 与 {state.lead_name} 的对话已达到 {MAX_TURNS} 轮上限。\n"
                f"最终意向: {state.stage} | 评分: {state.intent_score}/100\n"
                + ("✅ WhatsApp已推送" if state.whatsapp_sent else "❌ 未完成私域引导")
            )

        fb = _get_FacebookBrowser()()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return "❌ 未登录 Facebook。"

            # 读取最新消息
            replies = await fb.read_latest_replies(profile_url, since_count=5)

            # 找到客户的新回复
            new_reply = None
            for r in reversed(replies):
                if r["role"] == "them":
                    # 检查是否是新消息（不在已有记录中）
                    existing = [m["content"] for m in state.messages if m["role"] == "them"]
                    if r["content"] not in existing:
                        new_reply = r["content"]
                        break

            if not new_reply:
                return (
                    f"⏳ {state.lead_name} 暂无新回复。\n"
                    f"当前状态: 第{state.turn_count}轮 | {state.stage}\n"
                    f"建议稍后再检查。"
                )

            # 记录客户回复
            state.add_their_reply(new_reply)

            # AI 分析并生成回复
            result = generate_reply(state, new_reply)

            our_reply = result["reply"]
            state.stage = result["stage"]
            state.intent_score = result["intent_score"]
            state.intent_signals = result.get("intent_signals", [])

            if result.get("should_push_whatsapp"):
                state.whatsapp_sent = True

            # 发送回复（带重试）
            sent = await _send_dm_with_retry(fb, profile_url, our_reply)
            if sent:
                state.add_our_message(our_reply)

            stage_labels = {
                "cold": "❄️ 冷淡", "curious": "🤔 好奇", "interested": "👀 感兴趣",
                "qualified": "✅ 确认需求", "ready_to_connect": "🔥 准备转私域",
            }

            return (
                f"💬 与 {state.lead_name} 的对话更新\n"
                f"{'='*40}\n"
                f"← 客户说: {new_reply[:100]}\n"
                f"→ AI回复: {our_reply[:100]}\n\n"
                f"📊 轮次: {state.turn_count}/{MAX_TURNS}\n"
                f"🎯 意向: {stage_labels.get(state.stage, state.stage)} ({state.intent_score}分)\n"
                + (f"📌 意向信号: {', '.join(state.intent_signals)}\n" if state.intent_signals else "")
                + (f"✅ 已推送WhatsApp联系方式！\n" if state.whatsapp_sent else "")
                + f"💡 AI分析: {result.get('analysis', '')}\n"
                + (f"\n{'已发送' if sent else '⚠️ 发送失败，内容: ' + our_reply}" )
            )
        finally:
            await fb.close()

    return asyncio.run(_check())


@mcp.tool()
def manual_reply(lead_id: int, profile_url: str, message: str) -> str:
    """手动给客户发送一条私信（不使用AI生成）。

    当你想自己控制对话内容时使用。
    """
    async def _reply():
        state = ConversationState.load(str(lead_id))
        if not state:
            state = ConversationState(lead_id=str(lead_id), lead_name=f"Lead-{lead_id}")

        fb = _get_FacebookBrowser()()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return "❌ 未登录 Facebook。"
            sent = await fb.send_dm(profile_url, message)
            if sent:
                state.add_our_message(message)
                return f"✅ 已发送: {message[:80]}..."
            return "❌ 发送失败。"
        finally:
            await fb.close()

    return asyncio.run(_reply())


@mcp.tool()
def conversation_status(lead_id: int = 0) -> str:
    """查看对话状态。不传lead_id则列出所有活跃对话。

    示例: "看看我跟哪些客户在聊" / "客户5的对话进展如何"
    """
    if lead_id > 0:
        state = ConversationState.load(str(lead_id))
        if not state:
            return f"没有与客户 {lead_id} 的对话记录。"
        return get_conversation_summary(state)

    # 列出所有活跃对话
    convos = list_active_conversations()
    if not convos:
        return "暂无活跃对话。用 start_conversation 开始第一个对话吧。"

    stage_labels = {
        "cold": "❄️", "curious": "🤔", "interested": "👀",
        "qualified": "✅", "ready_to_connect": "🔥", "converted": "🎉",
    }

    lines = [f"📋 活跃对话列表 ({len(convos)} 个)：\n"]
    for c in convos:
        emoji = stage_labels.get(c["stage"], "❓")
        lines.append(
            f"  {emoji} [{c['lead_id']}] {c['lead_name']}"
            + (f" | {c['lead_company']}" if c.get("lead_company") else "")
            + f" | 第{c['turn_count']}轮 | 意向:{c['intent_score']}分"
            + (" | ✅WA已推" if c.get("whatsapp_sent") else "")
        )
    return "\n".join(lines)


@mcp.tool()
def auto_follow_up_all(concurrency: int = 5) -> str:
    """自动跟进所有活跃对话。检查所有客户的回复并自动回复。

    这是一个批量操作，会：
    1. 并发遍历所有活跃对话（默认5路并发）
    2. 检查每个客户是否有新回复
    3. 对有回复的客户自动用AI生成并发送回复
    4. 返回汇总结果

    参数:
    - concurrency: 并发数（默认5，建议不超过10避免Facebook风控）

    示例: "帮我跟进一下所有客户" / "检查所有对话"
    """
    async def _follow_up_all():
        convos = list_active_conversations()
        if not convos:
            return "暂无活跃对话。"

        # 过滤已达上限的对话
        active = [c for c in convos if c["turn_count"] < MAX_TURNS]
        if not active:
            return f"所有 {len(convos)} 个对话已达到 {MAX_TURNS} 轮上限。"

        # 预获取所有 lead 的 profile_url
        tasks_info = []
        for c in active:
            try:
                lead = _api("GET", f"/leads/{c['lead_id']}")
                profile_url = lead.get("source_url", "")
                if profile_url:
                    tasks_info.append((c, profile_url))
            except Exception:
                pass

        if not tasks_info:
            return "没有可跟进的对话（均缺少 profile_url）。"

        results = []
        semaphore = asyncio.Semaphore(concurrency)

        async def _process_one(conv_info, url):
            async with semaphore:
                try:
                    result = check_replies(int(conv_info["lead_id"]), url)
                    if "暂无新回复" not in result:
                        return f"• {conv_info['lead_name']}: 有新进展"
                    else:
                        return f"• {conv_info['lead_name']}: 等待回复中"
                except Exception as e:
                    return f"• {conv_info['lead_name']}: 检查失败 ({str(e)[:30]})"

        # 并发执行所有跟进任务
        coros = [_process_one(c, url) for c, url in tasks_info]
        results = await asyncio.gather(*coros)

        new_progress = sum(1 for r in results if "新进展" in r)
        waiting = sum(1 for r in results if "等待回复" in r)
        failed = sum(1 for r in results if "检查失败" in r)

        summary = (
            f"🔄 批量跟进完成 ({len(tasks_info)}/{len(convos)} 个对话，{concurrency}路并发)\n"
            f"   📈 新进展: {new_progress} | ⏳ 等待中: {waiting} | ❌ 失败: {failed}\n\n"
            + "\n".join(results)
        )
        return summary

    return asyncio.run(_follow_up_all())


@mcp.tool()
def full_pipeline(
    keyword: str,
    our_company: str = "",
    our_products: str = "",
    max_dm: int = 5,
    auto_dm: bool = True,
) -> str:
    """🚀 全自动获客流水线！从Facebook搜索到私信打招呼一步到位。

    完整流程:
    1. 操控浏览器在 Facebook 搜索目标客户
    2. AI 分析每个客户的买家意向评分
    3. 自动导入 LeadFlow 系统
    4. 给评分最高的客户发 Facebook 私信打招呼
    5. 进入 AI 自动对话模式（10轮内引导加WhatsApp）

    参数:
    - keyword: 搜索关键词，如 "LED lighting importer" 或 "electronics wholesale Southeast Asia"
    - our_company: 你的公司名称（用于AI生成个性化消息）
    - our_products: 你的产品描述
    - max_dm: 最多给几个客户发私信（默认5）
    - auto_dm: 是否自动发私信（false则只搜索不发）

    示例:
    - "帮我找做LED灯具的东南亚买家并打招呼"
    - "搜索电子产品进口商，我是深圳XX公司，做手机配件"
    """
    async def _pipeline():
        lines = [f"🚀 全自动获客启动: \"{keyword}\"\n"]

        # Step 1: Facebook 搜索
        lines.append("📡 Step 1/4: 在 Facebook 搜索目标客户...")
        search_result = await _get_find_customers()(
            query=keyword,
            search_type="all",
            max_results=20,
            headless=True,
            fb_email=FB_EMAIL,
            fb_password=FB_PASSWORD,
        )

        if not search_result["success"]:
            return f"❌ Facebook 搜索失败: {search_result['message']}"

        profiles = search_result["profiles"]
        groups = search_result["groups"]
        lines.append(f"   ✅ 找到 {len(profiles)} 个潜在客户" + (f"，{len(groups)} 个群组" if groups else ""))

        if not profiles:
            return "\n".join(lines) + "\n\n❌ 未找到潜在客户。试试换个关键词。"

        # Step 2: 导入 LeadFlow + AI 分析
        lines.append("\n🤖 Step 2/4: AI 分析客户意向...")
        imported_ids = []
        for p in profiles:
            try:
                lead = _api("POST", "/leads", json={
                    "name": p.get("name", "Unknown"),
                    "company": p.get("company", ""),
                    "phone": p.get("phone", ""),
                    "email": p.get("email", ""),
                    "source": "graph_api",
                    "source_url": p.get("profile_url", ""),
                    "profile_data": {
                        "bio": p.get("bio", ""),
                        "ai_reason": p.get("ai_reason", ""),
                        "search_query": keyword,
                    },
                    "language": p.get("language", "en"),
                })
                imported_ids.append(lead["id"])
            except Exception:
                continue

        # 批量 AI 深度分析
        analyzed = 0
        if imported_ids:
            try:
                result = _api("POST", "/leads/batch-analyze", json={"ids": imported_ids[:20]})
                analyzed = result.get("analyzed", 0)
            except Exception:
                pass

        lines.append(f"   ✅ 导入 {len(imported_ids)} 条线索，AI 分析了 {analyzed} 条")

        # Step 3: 筛选高分客户
        lines.append("\n🎯 Step 3/4: 筛选高质量客户...")
        qualified_data = _api("GET", "/leads", params={
            "min_score": 50,
            "sort_by": "score",
            "sort_order": "desc",
            "page_size": max_dm,
        })
        qualified = qualified_data.get("items", [])

        if not qualified:
            return "\n".join(lines) + "\n\n⚠️ 没有评分≥50的高质量客户。数据已导入，可手动查看。"

        lines.append(f"   ✅ {len(qualified)} 个高质量客户：")
        for i, q in enumerate(qualified[:max_dm], 1):
            lines.append(f"      {i}. {q['name']} | {q.get('company', '-')} | 评分:{q['score']:.0f}")

        # Step 4: 自动发私信
        if auto_dm:
            lines.append(f"\n💬 Step 4/4: 给 Top {min(max_dm, len(qualified))} 客户发 Facebook 私信...")

            fb = _get_FacebookBrowser()()
            dm_sent = 0
            try:
                await fb.start(headless=True)
                if not await fb.is_logged_in():
                    lines.append("   ⚠️ 未登录 Facebook，跳过私信。请先用 login_facebook 登录。")
                else:
                    for q in qualified[:max_dm]:
                        profile_url = q.get("source_url", "")
                        if not profile_url:
                            continue

                        # 创建对话状态
                        state = ConversationState(
                            lead_id=str(q["id"]),
                            lead_name=q["name"],
                            lead_company=q.get("company", ""),
                            lead_industry=q.get("profile_data", {}).get("industry", ""),
                            lead_language=q.get("language", "en"),
                            our_company=our_company,
                            our_products=our_products,
                        )

                        # AI 生成打招呼消息
                        opening = generate_opening_message(state)

                        # 发送私信（带重试）
                        sent = await _send_dm_with_retry(fb, profile_url, opening)
                        if sent:
                            state.add_our_message(opening)
                            dm_sent += 1
                            lines.append(f"   ✅ → {q['name']}: 私信已发送")

                            # 同步到后端
                            try:
                                _api("PUT", f"/leads/{q['id']}", json={"status": "contacted"})
                                _api("POST", "/conversations", json={
                                    "lead_id": q["id"],
                                    "profile_url": profile_url,
                                    "our_company": our_company,
                                    "our_products": our_products,
                                })
                            except Exception:
                                pass

                        # 间隔发送，避免风控
                        import asyncio as _aio
                        await _aio.sleep(3)

                    lines.append(f"\n   📨 共发送 {dm_sent} 条私信")
            finally:
                await fb.close()
        else:
            lines.append("\n⏸️ Step 4/4: 跳过自动私信（auto_dm=false）")
            lines.append("   使用 start_conversation 手动对指定客户发起私信。")

        # 汇总
        lines.append(f"\n{'='*40}")
        lines.append(f"📊 获客流水线完成！")
        lines.append(f"   搜索: {len(profiles)} 个客户")
        lines.append(f"   导入: {len(imported_ids)} 条线索")
        lines.append(f"   分析: {analyzed} 条")
        lines.append(f"   高质量: {len(qualified)} 个")
        if auto_dm:
            lines.append(f"   私信: {dm_sent} 条已发送")
        lines.append(f"\n⏳ 等待客户回复。说「检查回复」或「跟进所有客户」来推进对话。")
        lines.append(f"   AI 将在 10 轮对话内引导客户加 WhatsApp。")

        return "\n".join(lines)

    return asyncio.run(_pipeline())


# ============================================================
# WhatsApp 消息处理（客户已转私域后的对话）
# ============================================================


@mcp.tool()
def handle_whatsapp_message(
    phone: str,
    customer_name: str,
    message: str,
    our_company: str = "",
    our_products: str = "",
) -> str:
    """处理来自 WhatsApp 的客户消息，AI 生成回复。

    当客户通过 WhatsApp 给你发消息时，OpenClaw 会收到这条消息。
    调用这个工具让 AI 分析消息并生成合适的回复。

    OpenClaw 收到 WhatsApp 消息后应该自动调用此工具。

    参数:
    - phone: 客户手机号
    - customer_name: 客户名字
    - message: 客户发来的消息内容
    - our_company: 你的公司名（可选）
    - our_products: 你的产品（可选）

    返回 AI 生成的回复内容，OpenClaw 会通过 WhatsApp 发回给客户。

    内置速率限制（默认 20条/分钟、200条/小时），防止触发 WhatsApp API 封号。
    """
    # WhatsApp 限流检查
    if not _wa_limiter.can_send():
        wait = _wa_limiter.wait_time()
        return (
            f"⚠️ WhatsApp 发送已达速率限制（{WA_RATE_LIMIT_PER_MINUTE}条/分钟，{WA_RATE_LIMIT_PER_HOUR}条/小时）。\n"
            f"请等待 {wait:.0f} 秒后重试。\n\n"
            f"来自 {customer_name} ({phone}) 的消息已收到但暂未回复:\n{message[:100]}"
        )
    _wa_limiter.record_send()

    # 用 phone 作为 lead_id
    lead_id = f"wa_{phone.replace('+', '').replace(' ', '')}"

    # 加载或创建对话状态
    state = ConversationState.load(lead_id)
    if not state:
        state = ConversationState(
            lead_id=lead_id,
            lead_name=customer_name,
            lead_company="",
            lead_language="en",
            our_company=our_company,
            our_products=our_products,
        )
        state.stage = "interested"  # WhatsApp 客户已经是高意向了
        state.intent_score = 60

    # 记录客户消息
    state.add_their_reply(message)

    # AI 生成回复
    result = generate_reply(state, message)
    our_reply = result["reply"]
    state.stage = result["stage"]
    state.intent_score = result["intent_score"]
    state.intent_signals = result.get("intent_signals", [])
    state.add_our_message(our_reply)

    # 同步到 LeadFlow 后端
    try:
        # 查找或创建线索
        leads_data = _api("GET", "/leads", params={"search": phone, "page_size": 1})
        if leads_data.get("items"):
            lead = leads_data["items"][0]
            _api("PUT", f"/leads/{lead['id']}", json={"status": "replied"})
        else:
            _api("POST", "/leads", json={
                "name": customer_name,
                "phone": phone,
                "source": "csv",
                "profile_data": {"channel": "whatsapp"},
            })
    except Exception:
        pass

    stage_labels = {
        "cold": "❄️ 冷淡", "curious": "🤔 好奇", "interested": "👀 感兴趣",
        "qualified": "✅ 确认需求", "ready_to_connect": "🔥 准备成交",
        "converted": "🎉 已转化",
    }

    # 返回给 OpenClaw，OpenClaw 会把这个回复通过 WhatsApp 发给客户
    return (
        f"REPLY_TO_CUSTOMER:\n{our_reply}\n\n"
        f"---\n"
        f"📊 对话分析:\n"
        f"  客户: {customer_name} ({phone})\n"
        f"  轮次: {state.turn_count}/{MAX_TURNS}\n"
        f"  意向: {stage_labels.get(state.stage, state.stage)} ({state.intent_score}分)\n"
        + (f"  信号: {', '.join(state.intent_signals)}\n" if state.intent_signals else "")
        + f"  AI分析: {result.get('analysis', '')}"
    )


@mcp.tool()
def get_whatsapp_reply_suggestion(
    phone: str,
    customer_name: str,
    message: str,
) -> str:
    """获取 AI 建议的回复但不自动发送。用于你想先看看 AI 建议再决定怎么回。

    和 handle_whatsapp_message 的区别：这个只返回建议，不记录对话历史。
    你可以修改后再手动发送。
    """
    lead_id = f"wa_{phone.replace('+', '').replace(' ', '')}"
    state = ConversationState.load(lead_id)
    if not state:
        state = ConversationState(
            lead_id=lead_id,
            lead_name=customer_name,
            lead_language="en",
        )
        state.stage = "interested"

    result = generate_reply(state, message)

    return (
        f"💡 AI 建议回复:\n\n{result['reply']}\n\n"
        f"---\n"
        f"意向判断: {result['stage']} ({result['intent_score']}分)\n"
        f"分析: {result.get('analysis', '')}\n\n"
        f"⚠️ 这只是建议，不会自动发送。你可以修改后手动回复。"
    )


@mcp.tool()
def whatsapp_conversation_list() -> str:
    """列出所有通过 WhatsApp 进行的对话及其状态。"""
    convos = list_active_conversations()
    wa_convos = [c for c in convos if str(c["lead_id"]).startswith("wa_")]

    if not wa_convos:
        return "暂无 WhatsApp 对话记录。"

    stage_labels = {
        "cold": "❄️", "curious": "🤔", "interested": "👀",
        "qualified": "✅", "ready_to_connect": "🔥", "converted": "🎉",
    }

    lines = [f"📱 WhatsApp 对话列表 ({len(wa_convos)} 个):\n"]
    for c in wa_convos:
        emoji = stage_labels.get(c["stage"], "❓")
        phone = c["lead_id"].replace("wa_", "+")
        lines.append(
            f"  {emoji} {c['lead_name']} ({phone})\n"
            f"     第{c['turn_count']}轮 | 意向:{c['intent_score']}分\n"
            f"     最新: {c.get('last_message', '')[:40]}..."
        )
    return "\n".join(lines)


@mcp.tool()
def whatsapp_rate_status() -> str:
    """查看 WhatsApp 发送速率限制状态。

    显示当前限额使用情况和剩余配额。
    """
    now = time.time()
    _wa_limiter._cleanup(now)

    one_min_ago = now - 60
    recent_min = sum(1 for ts in _wa_limiter._timestamps if ts > one_min_ago)
    total_hour = len(_wa_limiter._timestamps)

    return (
        f"📊 WhatsApp 速率限制状态\n"
        f"{'='*35}\n"
        f"每分钟: {recent_min}/{_wa_limiter.per_minute} 条\n"
        f"每小时: {total_hour}/{_wa_limiter.per_hour} 条\n"
        f"可立即发送: {'✅ 是' if _wa_limiter.can_send() else '❌ 否'}\n"
        + (f"需等待: {_wa_limiter.wait_time():.0f} 秒\n" if not _wa_limiter.can_send() else "")
        + f"\n配置: WA_RATE_LIMIT_PER_MINUTE={WA_RATE_LIMIT_PER_MINUTE}, WA_RATE_LIMIT_PER_HOUR={WA_RATE_LIMIT_PER_HOUR}"
    )


# ============================================================
# 人设管理
# ============================================================


@mcp.tool()
def view_persona() -> str:
    """查看当前 AI 人设配置。"""
    persona_file = Path(__file__).parent / "persona.json"
    if not persona_file.exists():
        return "❌ 人设文件不存在"
    persona = json.loads(persona_file.read_text(encoding="utf-8"))
    company = persona.get("company", {})
    sales = persona.get("salesperson", {})
    style = persona.get("conversation_style", {})

    return (
        f"🎭 当前 AI 人设\n"
        f"{'='*40}\n"
        f"\n🏢 公司:\n"
        f"  名称: {company.get('name', '未设置')}\n"
        f"  英文名: {company.get('name_en', '未设置')}\n"
        f"  产品: {company.get('products', '未设置')}\n"
        f"  优势: {', '.join(company.get('advantages', []))}\n"
        f"\n👤 销售人设:\n"
        f"  姓名: {sales.get('name', '未设置')}\n"
        f"  职位: {sales.get('title', '未设置')}\n"
        f"  性格: {sales.get('personality', '未设置')}\n"
        f"  WhatsApp: {sales.get('whatsapp', '未设置')}\n"
        f"\n💬 对话风格:\n"
        f"  语气: {style.get('tone', '未设置')}\n"
        f"  消息长度: {style.get('max_message_length', 200)}字\n"
        f"\n修改人设: 使用 update_persona 工具"
    )


@mcp.tool()
def update_persona(
    company_name: str = "",
    company_name_en: str = "",
    products: str = "",
    advantages: str = "",
    sales_name: str = "",
    sales_title: str = "",
    personality: str = "",
    whatsapp: str = "",
    tone: str = "",
    max_message_length: int = 0,
) -> str:
    """修改 AI 人设。只传你想改的字段，不传的保持不变。

    示例:
    - "把公司名改成深圳光明科技" → company_name="深圳光明科技"
    - "销售人设改成 Amy，热情开朗" → sales_name="Amy", personality="热情开朗，善于用emoji"
    - "产品改成太阳能路灯" → products="太阳能路灯、庭院灯、景观照明"
    - "WhatsApp 号码改成 +86139xxxx" → whatsapp="+86139xxxx"
    - "语气改成更轻松活泼" → tone="casual_warm"

    tone 可选: professional_friendly / casual_warm / formal_business
    """
    persona_file = Path(__file__).parent / "persona.json"
    persona = json.loads(persona_file.read_text(encoding="utf-8")) if persona_file.exists() else {}

    changes = []

    if company_name:
        persona.setdefault("company", {})["name"] = company_name
        changes.append(f"公司名 → {company_name}")
    if company_name_en:
        persona.setdefault("company", {})["name_en"] = company_name_en
        changes.append(f"英文名 → {company_name_en}")
    if products:
        persona.setdefault("company", {})["products"] = products
        changes.append(f"产品 → {products}")
    if advantages:
        persona.setdefault("company", {})["advantages"] = [a.strip() for a in advantages.split(",")]
        changes.append(f"优势 → {advantages}")
    if sales_name:
        persona.setdefault("salesperson", {})["name"] = sales_name
        changes.append(f"销售姓名 → {sales_name}")
    if sales_title:
        persona.setdefault("salesperson", {})["title"] = sales_title
        changes.append(f"职位 → {sales_title}")
    if personality:
        persona.setdefault("salesperson", {})["personality"] = personality
        changes.append(f"性格 → {personality}")
    if whatsapp:
        persona.setdefault("salesperson", {})["whatsapp"] = whatsapp
        changes.append(f"WhatsApp → {whatsapp}")
    if tone:
        persona.setdefault("conversation_style", {})["tone"] = tone
        changes.append(f"语气 → {tone}")
    if max_message_length > 0:
        persona.setdefault("conversation_style", {})["max_message_length"] = max_message_length
        changes.append(f"消息长度 → {max_message_length}字")

    if not changes:
        return "没有传入任何修改。请指定要改的字段。"

    persona_file.write_text(json.dumps(persona, ensure_ascii=False, indent=2), encoding="utf-8")

    return (
        f"✅ 人设已更新（立即生效）:\n\n"
        + "\n".join(f"  • {c}" for c in changes)
        + "\n\n下一条消息将使用新人设。"
    )


# ============================================================
# 浏览器后端管理
# ============================================================


@mcp.tool()
def browser_status() -> str:
    """查看当前浏览器后端状态。

    显示当前使用的是 OpenCLI（复用Chrome登录态）还是 Playwright（独立浏览器）。
    """
    async def _status():
        opencli_ready = await browser_agent_opencli.is_opencli_ready()
        pw_available = True
        try:
            import playwright
        except ImportError:
            pw_available = False

        current = "auto"
        if _browser_backend != "auto":
            current = _browser_backend
        elif opencli_ready:
            current = "opencli (auto)"
        else:
            current = "playwright (auto fallback)"

        lines = [
            f"🔧 浏览器后端状态\n",
            f"当前模式: {current}",
            f"",
            f"OpenCLI:    {'✅ 就绪' if opencli_ready else '❌ 未连接'}",
            f"  - 复用 Chrome 已登录的 Facebook，不易被检测",
            f"  - 需要: Chrome + OpenCLI 扩展",
            f"",
            f"Playwright: {'✅ 已安装' if pw_available else '❌ 未安装'}",
            f"  - 启动独立浏览器，需要重新登录 Facebook",
            f"  - 备选方案",
        ]

        if not opencli_ready:
            lines.extend([
                f"",
                f"💡 推荐安装 OpenCLI:",
                f"  npm install -g @jackwener/opencli",
                f"  然后在 Chrome 中安装 Browser Bridge 扩展",
            ])

        return "\n".join(lines)

    return asyncio.run(_status())


@mcp.tool()
def switch_browser_backend(backend: str = "auto") -> str:
    """切换浏览器后端。

    可选:
    - "auto": 自动选择（优先 OpenCLI）
    - "opencli": 强制使用 OpenCLI（复用 Chrome）
    - "playwright": 强制使用 Playwright（独立浏览器）
    """
    global _browser_backend
    if backend not in ("auto", "opencli", "playwright"):
        return f"❌ 无效的后端: {backend}。可选: auto, opencli, playwright"
    _browser_backend = backend
    return f"✅ 浏览器后端已切换为: {backend}"


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    print("🦞 LeadFlow MCP Server starting...")
    print(f"   Backend: {LEADFLOW_BASE_URL}")
    print(f"   Account: {LEADFLOW_EMAIL}")

    # 检测浏览器后端
    import asyncio as _aio
    _opencli_ok = _aio.run(browser_agent_opencli.is_opencli_ready())
    print(f"   Browser: {'OpenCLI (Chrome)' if _opencli_ok else 'Playwright (fallback)'}")

    print("   Ready for OpenClaw connection.")
    mcp.run(transport="stdio")
