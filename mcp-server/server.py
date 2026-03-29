"""LeadFlow AI MCP Server — 为 OpenClaw 提供社媒获客工具集"""

import os

from mcp.server.fastmcp import FastMCP
import httpx

mcp = FastMCP("leadflow")
API_BASE = os.getenv("LEADFLOW_API_URL", "http://localhost:8000")

# Auth: login once at startup and reuse token
_auth_token: str | None = None


async def _ensure_auth():
    """Login to backend and cache the token."""
    global _auth_token
    if _auth_token:
        return
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{API_BASE}/api/auth/login", json={
            "email": "admin@leadflow.ai",
            "password": os.getenv("LEADFLOW_ADMIN_PASSWORD", "admin123456"),
        })
        resp.raise_for_status()
        _auth_token = resp.json()["access_token"]


async def _request(method: str, path: str, **kwargs) -> dict | list:
    """统一请求后端 API（带认证）"""
    await _ensure_auth()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(
            method,
            f"{API_BASE}/api{path}",
            headers={"Authorization": f"Bearer {_auth_token}"},
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def create_campaign(
    platform: str,
    keywords: str,
    region: str = "",
    industry: str = "",
    persona_id: int = 0,
    send_limit: int = 20,
) -> str:
    """创建一个新的社媒线索搜索任务。平台支持: facebook"""
    payload = {
        "platform": platform,
        "search_keywords": keywords,
        "search_region": region,
        "search_industry": industry,
        "send_limit": send_limit,
    }
    if persona_id:
        payload["persona_id"] = persona_id
    data = await _request("POST", "/campaigns", json=payload)
    return (
        f"任务创建成功!\n"
        f"- 任务 ID: {data.get('id')}\n"
        f"- 平台: {data.get('platform')}\n"
        f"- 关键词: {data.get('search_keywords')}\n"
        f"- 状态: {data.get('status')}\n"
        f"- 发送上限: {data.get('send_limit')}"
    )


@mcp.tool()
async def start_campaign(campaign_id: int) -> str:
    """启动一个已创建的任务"""
    data = await _request("POST", f"/campaigns/{campaign_id}/start")
    return f"任务 #{campaign_id} 已启动。{data.get('message', '')}"


@mcp.tool()
async def pause_campaign(campaign_id: int) -> str:
    """暂停正在运行的任务"""
    data = await _request("POST", f"/campaigns/{campaign_id}/pause")
    return f"任务 #{campaign_id} 已暂停。{data.get('message', '')}"


@mcp.tool()
async def get_campaign_status(campaign_id: int) -> str:
    """查看任务进度和状态"""
    data = await _request("GET", f"/campaigns/{campaign_id}")
    leads = data.get("leads", [])
    return (
        f"任务 #{data.get('id')} 状态报告\n"
        f"- 平台: {data.get('platform')}\n"
        f"- 关键词: {data.get('search_keywords')}\n"
        f"- 状态: {data.get('status')}\n"
        f"- 进度: {data.get('progress_current', 0)} / {data.get('progress_total', 0)}\n"
        f"- 线索数: {len(leads)}\n"
        f"- 创建时间: {data.get('created_at')}"
    )


@mcp.tool()
async def list_campaigns() -> str:
    """列出所有任务"""
    data = await _request("GET", "/campaigns")
    if not data:
        return "暂无任务。使用 create_campaign 创建第一个任务。"
    lines = ["所有任务列表:\n"]
    for c in data:
        lines.append(
            f"  [{c.get('id')}] {c.get('platform')} | "
            f"关键词: {c.get('search_keywords')} | "
            f"状态: {c.get('status')} | "
            f"进度: {c.get('progress_current', 0)}/{c.get('send_limit')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_leads(campaign_id: int = 0, status: str = "") -> str:
    """查看线索列表，可按任务ID或状态筛选"""
    params = {}
    if campaign_id:
        params["campaign_id"] = str(campaign_id)
    if status:
        params["status"] = status
    data = await _request("GET", "/leads", params=params)
    if not data:
        return "暂无匹配的线索。"
    lines = [f"共 {len(data)} 条线索:\n"]
    for lead in data:
        lines.append(
            f"  - {lead.get('name', '未知')} | "
            f"平台: {lead.get('platform')} | "
            f"状态: {lead.get('status')} | "
            f"任务: #{lead.get('campaign_id')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def search_and_message(
    platform: str,
    keywords: str,
    region: str = "",
    industry: str = "",
    send_limit: int = 10,
) -> str:
    """一键搜索并发送问好消息（创建任务+自动启动）"""
    payload = {
        "platform": platform,
        "search_keywords": keywords,
        "search_region": region,
        "search_industry": industry,
        "send_limit": send_limit,
    }
    campaign = await _request("POST", "/campaigns", json=payload)
    campaign_id = campaign.get("id")

    await _request("POST", f"/campaigns/{campaign_id}/start")

    return (
        f"一键任务已启动!\n"
        f"- 任务 ID: {campaign_id}\n"
        f"- 平台: {platform}\n"
        f"- 关键词: {keywords}\n"
        f"- 地区: {region or '不限'}\n"
        f"- 行业: {industry or '不限'}\n"
        f"- 发送上限: {send_limit}\n\n"
        f"任务正在后台运行，使用 get_campaign_status({campaign_id}) 查看进度。"
    )


if __name__ == "__main__":
    mcp.run()
