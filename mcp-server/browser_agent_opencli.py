"""
Facebook 浏览器自动化 Agent — OpenCLI 版本

通过 OpenCLI 控制用户已登录的 Chrome 浏览器，在 Facebook 上搜索潜在客户。
与 browser_agent.py (Playwright) 接口一致，作为优先方案使用。

优势：
- 复用用户已登录的 Chrome，无需重新登录 Facebook
- 真实浏览器环境，不易被 Facebook 检测
- 无需下载额外的 Chromium (~400MB)

前提：
- npm install -g @jackwener/opencli
- Chrome 已安装 OpenCLI Browser Bridge 扩展
- Chrome 已登录 Facebook
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import uuid
from typing import Any

from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DAEMON_URL = "http://127.0.0.1:19825"
DAEMON_HEADERS = {"X-OpenCLI": "1", "Content-Type": "application/json"}

# 自动加载 backend/.env（MCP server 运行在主机上）
_env_file = Path(__file__).parent.parent / "backend" / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k = _k.strip()
            _v = _v.strip()
            if _k and not os.environ.get(_k):
                os.environ[_k] = _v

AI_PROVIDER = os.environ.get("AI_PROVIDER", "kimi")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-k2.5")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o")


# ============================================================
# OpenCLI Daemon 通信
# ============================================================

async def _daemon_command(action: str, timeout: float = 30, **kwargs) -> Any:
    """向 OpenCLI daemon 发送命令。"""
    payload = {"id": str(uuid.uuid4()), "action": action, **kwargs}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{DAEMON_URL}/command",
            json=payload,
            headers=DAEMON_HEADERS,
        )
        result = resp.json()
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "Unknown daemon error"))
        return result.get("data")


async def _daemon_status() -> dict:
    """检查 daemon 状态。"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{DAEMON_URL}/status")
            return resp.json()
    except Exception:
        return {"ok": False, "extensionConnected": False}


def _opencli_available() -> bool:
    """检查 opencli 是否已安装。"""
    try:
        result = subprocess.run(
            ["opencli", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


async def _ensure_daemon() -> bool:
    """确保 daemon 正在运行且扩展已连接。"""
    status = await _daemon_status()
    if status.get("ok") and status.get("extensionConnected"):
        return True

    # 尝试通过运行一个简单命令来自动启动 daemon
    if _opencli_available():
        try:
            subprocess.Popen(
                ["opencli", "doctor"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # 等 daemon 启动
            for _ in range(10):
                await asyncio.sleep(1)
                status = await _daemon_status()
                if status.get("ok") and status.get("extensionConnected"):
                    return True
        except Exception:
            pass

    return False


# ============================================================
# AI 辅助（复用 browser_agent 的逻辑）
# ============================================================

def _get_ai_config() -> tuple[str, str, str] | None:
    """返回可用的 AI 配置 (api_key, base_url, model)，按 AI_PROVIDER 优先。"""
    provider = AI_PROVIDER.lower()
    configs = {
        "kimi": (KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL),
        "openai": (OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL),
        "openrouter": (OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL),
    }
    # 优先使用指定 provider
    if provider in configs and configs[provider][0]:
        return configs[provider]
    # 回退：找任意可用的
    for cfg in configs.values():
        if cfg[0]:
            return cfg
    return None


async def ai_analyze_profiles(profiles: list[dict], search_context: str) -> list[dict]:
    """用 AI 分析提取到的 profile 数据，判断是否为潜在买家。"""
    ai_cfg = _get_ai_config()
    if not ai_cfg or not profiles:
        return profiles

    api_key, base_url, model = ai_cfg
    profiles_text = json.dumps(profiles[:20], ensure_ascii=False, indent=2)
    prompt = f"""你是一个B2B外贸获客助手。我在Facebook上搜索了「{search_context}」，找到了以下用户资料。

请分析每个人，判断他们是否可能是B2B买家（进口商、批发商、采购经理等）。
给每个人一个0-100的意向评分，并用一句话说明理由。

用户资料:
{profiles_text}

请返回JSON数组格式:
[
  {{"name": "...", "company": "...", "score": 75, "reason": "...", "language": "en"}},
  ...
]

只返回JSON，不要其他内容。"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            analyzed = json.loads(text)

            for i, item in enumerate(analyzed):
                if i < len(profiles):
                    profiles[i]["score"] = item.get("score", 50)
                    profiles[i]["ai_reason"] = item.get("reason", "")
                    profiles[i]["language"] = item.get("language", "en")

            return profiles
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return profiles


# ============================================================
# Facebook 浏览器操作 — OpenCLI 版
# ============================================================

class FacebookBrowser:
    """通过 OpenCLI 控制用户已登录的 Chrome 在 Facebook 上搜索客户。"""

    def __init__(self):
        self._workspace = f"fb_{uuid.uuid4().hex[:8]}"
        self._connected = False

    async def start(self, headless: bool = False):
        """连接到 OpenCLI daemon（忽略 headless 参数，始终用用户的 Chrome）。"""
        connected = await _ensure_daemon()
        if not connected:
            raise RuntimeError(
                "OpenCLI daemon 未连接。请确保：\n"
                "1. Chrome 已安装 OpenCLI Browser Bridge 扩展\n"
                "2. Chrome 正在运行\n"
                "3. 运行 opencli doctor 检查状态"
            )
        self._connected = True

    async def close(self):
        """清理。OpenCLI 不需要关闭浏览器，只清理 workspace。"""
        self._connected = False

    async def _navigate(self, url: str, settle_ms: int = 3000):
        """导航到指定 URL。"""
        await _daemon_command(
            "navigate", url=url, workspace=self._workspace, timeout=20,
        )
        # 等待页面稳定
        await asyncio.sleep(settle_ms / 1000)

    async def _evaluate(self, js: str, timeout: float = 15) -> Any:
        """在当前页面执行 JS 并返回结果。"""
        return await _daemon_command(
            "exec", code=js, workspace=self._workspace, timeout=timeout,
        )

    async def _scroll_down(self, times: int = 3, delay: float = 1.5):
        """向下滚动页面加载更多内容。"""
        for _ in range(times):
            await self._evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(delay)

    async def is_logged_in(self) -> bool:
        """检查 Chrome 是否已登录 Facebook。"""
        try:
            await self._navigate("https://www.facebook.com/", settle_ms=2000)
            result = await self._evaluate(
                "!!document.querySelector('[aria-label=\"Search Facebook\"]')"
            )
            return bool(result)
        except Exception:
            return False

    async def login(self, email: str, password: str) -> bool:
        """OpenCLI 方案下不需要程序化登录 — 用户已在 Chrome 中登录。"""
        logger.info(
            "OpenCLI 模式下请在 Chrome 浏览器中手动登录 Facebook。"
            "登录后状态会自动保持。"
        )
        return await self.is_logged_in()

    async def search_people(self, query: str, max_results: int = 20) -> list[dict]:
        """在 Facebook 上搜索 People。"""
        results = []
        try:
            # 先尝试 opencli 内置命令
            results = await self._opencli_facebook_search(query, max_results)
            if results:
                return results

            # 回退到手动导航 + JS 提取
            search_url = f"https://www.facebook.com/search/people/?q={query}"
            await self._navigate(search_url, settle_ms=3000)
            await self._scroll_down(3)

            js = """
            (() => {
                const results = [];
                const seen = new Set();
                const cards = document.querySelectorAll('[role="article"], [data-visualcompletion="ignore-dynamic"]');
                for (const card of cards) {
                    const link = card.querySelector('a[href*="facebook.com/"]');
                    const text = card.innerText || '';
                    const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
                    if (!lines.length) continue;
                    const name = lines[0];
                    if (seen.has(name) || name.length < 2 || name.length > 60) continue;
                    seen.add(name);

                    let company = '';
                    let bio = '';
                    for (const line of lines.slice(1)) {
                        if (/works? at|ceo|founder|manager|director|owner/i.test(line)) {
                            company = line;
                        } else if (line.length > 10 && !bio) {
                            bio = line;
                        }
                    }

                    results.push({
                        name,
                        company,
                        bio,
                        profile_url: link ? link.href : '',
                        source: 'facebook_people_search',
                        phone: '',
                        email: '',
                    });
                }
                return results.slice(0, """ + str(max_results) + """);
            })()
            """
            data = await self._evaluate(js)
            if isinstance(data, list):
                results = data

            # 备用提取
            if not results:
                results = await self._extract_links_fallback(max_results)

        except Exception as e:
            logger.error(f"Facebook people search failed: {e}")

        return results

    async def search_pages(self, query: str, max_results: int = 20) -> list[dict]:
        """在 Facebook 上搜索 Pages（公司/品牌页面）。"""
        results = []
        try:
            search_url = f"https://www.facebook.com/search/pages/?q={query}"
            await self._navigate(search_url, settle_ms=3000)
            await self._scroll_down(3)

            js = """
            (() => {
                const results = [];
                const seen = new Set();
                const skip = ['log in','sign up','facebook','people','photos','videos','posts','groups'];
                const links = document.querySelectorAll('a[href*="facebook.com/"]');
                for (const link of links) {
                    const text = (link.innerText || '').trim();
                    const href = link.href || '';
                    if (!text || text.length < 2 || text.length > 100) continue;
                    if (seen.has(text) || href.includes('facebook.com/search')) continue;
                    if (skip.some(s => text.toLowerCase().includes(s))) continue;
                    seen.add(text);
                    results.push({
                        name: text,
                        company: text,
                        profile_url: href,
                        source: 'facebook_page_search',
                        phone: '',
                        email: '',
                    });
                }
                return results.slice(0, """ + str(max_results) + """);
            })()
            """
            data = await self._evaluate(js)
            if isinstance(data, list):
                results = data

        except Exception as e:
            logger.error(f"Facebook page search failed: {e}")

        return results

    async def search_groups(self, query: str, max_results: int = 10) -> list[dict]:
        """在 Facebook 上搜索 Groups。"""
        results = []
        try:
            search_url = f"https://www.facebook.com/search/groups/?q={query}"
            await self._navigate(search_url, settle_ms=3000)

            js = """
            (() => {
                const results = [];
                const seen = new Set();
                const links = document.querySelectorAll('a[href*="/groups/"]');
                for (const link of links) {
                    const text = (link.innerText || '').trim();
                    const href = link.href || '';
                    if (!text || text.length < 3 || seen.has(text)) continue;
                    if (href.includes('search') || href.includes('groups/?q')) continue;
                    seen.add(text);
                    results.push({ name: text, group_url: href, type: 'group' });
                }
                return results.slice(0, """ + str(max_results) + """);
            })()
            """
            data = await self._evaluate(js)
            if isinstance(data, list):
                results = data

        except Exception as e:
            logger.error(f"Facebook group search failed: {e}")

        return results

    async def extract_group_members(self, group_url: str, max_members: int = 20) -> list[dict]:
        """进入一个 Facebook Group，提取活跃成员信息。"""
        results = []
        try:
            members_url = group_url.rstrip("/") + "/members"
            await self._navigate(members_url, settle_ms=3000)
            await self._scroll_down(3)

            js = """
            (() => {
                const results = [];
                const seen = new Set();
                const links = document.querySelectorAll('a[href*="facebook.com/"]');
                for (const link of links) {
                    const text = (link.innerText || '').trim();
                    const href = link.href || '';
                    if (!text || text.length < 2 || text.length > 60 || seen.has(text)) continue;
                    if (href.includes('/groups/') || href.includes('/search') || href.includes('?__cft__')) continue;
                    seen.add(text);
                    results.push({
                        name: text,
                        profile_url: href,
                        source: 'facebook_group',
                        company: '',
                        phone: '',
                        email: '',
                    });
                }
                return results.slice(0, """ + str(max_members) + """);
            })()
            """
            data = await self._evaluate(js)
            if isinstance(data, list):
                results = data

        except Exception as e:
            logger.error(f"Group member extraction failed: {e}")

        return results

    async def visit_profile(self, profile_url: str) -> dict:
        """访问用户 Profile 页面，提取详细信息。"""
        info = {"profile_url": profile_url}
        try:
            about_url = profile_url.rstrip("/") + "/about"
            await self._navigate(about_url, settle_ms=2000)

            js = """
            (() => {
                const body = document.body.innerText || '';
                const title = document.title || '';
                const info = {};

                // 名字
                if (title.includes('|')) {
                    info.name = title.split('|')[0].trim();
                } else {
                    info.name = title.replace(' | Facebook', '').trim();
                }

                // 工作
                const workMatch = body.match(/Works? at (.+?)(?:\\n|$)/i)
                    || body.match(/(?:CEO|Founder|Manager|Director|Owner) (?:at|of) (.+?)(?:\\n|$)/i);
                if (workMatch) info.company = workMatch[1].trim();

                // 位置
                const locMatch = body.match(/Lives in (.+?)(?:\\n|$)/i);
                if (locMatch) info.location = locMatch[1].trim();

                // 简介
                const bioMatch = body.match(/Bio\\n(.+?)(?:\\n|$)/);
                if (bioMatch) info.bio = bioMatch[1].trim();

                // 电话
                const phoneMatch = body.match(/(\\+?\\d[\\d\\s\\-]{8,15})/);
                if (phoneMatch) info.phone = phoneMatch[1].trim();

                // 邮箱
                const emailMatch = body.match(/[\\w.+-]+@[\\w-]+\\.[\\w.-]+/);
                if (emailMatch) info.email = emailMatch[0];

                return info;
            })()
            """
            data = await self._evaluate(js)
            if isinstance(data, dict):
                info.update(data)

        except Exception as e:
            logger.error(f"Profile extraction failed: {e}")

        return info

    async def send_dm(self, profile_url: str, message: str) -> bool:
        """给 Facebook 用户发送私信。"""
        try:
            # 先尝试直接去 Messenger
            username = profile_url.rstrip("/").split("/")[-1]
            messenger_url = f"https://www.facebook.com/messages/t/{username}"
            await self._navigate(messenger_url, settle_ms=3000)

            # 查找输入框并输入消息
            # 使用 execCommand 输入文本到 contenteditable div
            escaped_msg = json.dumps(message)
            js = f"""
            (() => {{
                const input = document.querySelector(
                    '[aria-label*="Message"], [aria-label*="message"], '
                    + '[role="textbox"], div[contenteditable="true"]'
                );
                if (!input) return {{ success: false, error: 'no_input_box' }};

                input.focus();
                input.click();

                // 输入消息
                const lines = {escaped_msg}.split('\\n');
                for (let i = 0; i < lines.length; i++) {{
                    document.execCommand('insertText', false, lines[i]);
                    if (i < lines.length - 1) {{
                        // Shift+Enter 换行
                        input.dispatchEvent(new KeyboardEvent('keydown', {{
                            key: 'Enter', code: 'Enter', shiftKey: true, bubbles: true
                        }}));
                    }}
                }}

                return {{ success: true }};
            }})()
            """
            result = await self._evaluate(js)
            if not result or not result.get("success"):
                logger.error(f"Could not find message input: {result}")
                return False

            await asyncio.sleep(0.5)

            # 按 Enter 发送
            send_js = """
            (() => {
                const input = document.querySelector(
                    '[role="textbox"], div[contenteditable="true"]'
                );
                if (input) {
                    input.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Enter', code: 'Enter', shiftKey: false, bubbles: true
                    }));
                    return true;
                }
                return false;
            })()
            """
            await self._evaluate(send_js)
            await asyncio.sleep(2)

            logger.info(f"DM sent to {profile_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to send DM to {profile_url}: {e}")
            return False

    async def read_latest_replies(self, profile_url: str, since_count: int = 5) -> list[dict]:
        """读取与某用户的最新消息。"""
        replies = []
        try:
            username = profile_url.rstrip("/").split("/")[-1]
            messenger_url = f"https://www.facebook.com/messages/t/{username}"
            await self._navigate(messenger_url, settle_ms=3000)

            js = f"""
            (() => {{
                const replies = [];
                const rows = document.querySelectorAll('[role="row"], [data-scope="messages_table"], div[class*="message"]');
                const items = Array.from(rows).slice(-{since_count});
                for (const row of items) {{
                    const text = (row.innerText || '').trim();
                    if (!text) continue;
                    const cls = (row.className || '').toLowerCase();
                    const isOurs = cls.includes('blue') || cls.includes('outgoing');
                    replies.push({{ role: isOurs ? 'us' : 'them', content: text }});
                }}
                return replies;
            }})()
            """
            data = await self._evaluate(js)
            if isinstance(data, list):
                replies = data

        except Exception as e:
            logger.error(f"Failed to read replies from {profile_url}: {e}")

        return replies

    async def check_unread_messages(self) -> list[dict]:
        """检查 Messenger 中的未读消息。"""
        unread = []
        try:
            await self._navigate("https://www.facebook.com/messages/", settle_ms=3000)

            js = """
            (() => {
                const unread = [];
                const threads = document.querySelectorAll('a[href*="/messages/t/"]');
                for (const thread of Array.from(threads).slice(0, 20)) {
                    const text = (thread.innerText || '').trim();
                    const href = thread.href || '';
                    const parent = thread.parentElement;
                    const cls = parent ? (parent.className || '').toLowerCase() : '';
                    if (cls.includes('unread') || cls.includes('bold')) {
                        unread.push({ thread_url: href, preview: text.slice(0, 100) });
                    }
                }
                return unread;
            })()
            """
            data = await self._evaluate(js)
            if isinstance(data, list):
                unread = data

        except Exception as e:
            logger.error(f"Failed to check unread messages: {e}")

        return unread

    async def take_screenshot(self, filename: str = "screenshot.png") -> str:
        """截图当前页面。"""
        try:
            data = await _daemon_command("screenshot", workspace=self._workspace)
            if data:
                import base64
                from pathlib import Path
                path = Path.home() / ".leadflow" / "fb-state" / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(data))
                return str(path)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
        return ""

    # --- 内部辅助方法 ---

    async def _opencli_facebook_search(self, query: str, max_results: int) -> list[dict]:
        """尝试用 opencli 内置的 facebook search 命令。"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "opencli", "facebook", "search", query,
                "--limit", str(max_results), "-f", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0 and stdout:
                data = json.loads(stdout.decode())
                if isinstance(data, list):
                    return [
                        {
                            "name": item.get("title", item.get("name", "")),
                            "company": item.get("company", ""),
                            "bio": item.get("snippet", item.get("content", "")),
                            "profile_url": item.get("url", item.get("link", "")),
                            "source": "facebook_people_search",
                            "phone": "",
                            "email": "",
                        }
                        for item in data
                        if item.get("title") or item.get("name")
                    ]
        except Exception as e:
            logger.debug(f"opencli facebook search fallback: {e}")
        return []

    async def _extract_links_fallback(self, max_results: int) -> list[dict]:
        """备用：从页面链接中提取信息。"""
        js = f"""
        (() => {{
            const results = [];
            const seen = new Set();
            const links = document.querySelectorAll('a[role="presentation"], a[href*="facebook.com/"]');
            for (const link of links) {{
                const text = (link.innerText || '').trim();
                const href = link.href || '';
                if (text && text.length > 2 && text.length < 60 && !seen.has(text)) {{
                    if (!href.includes('facebook.com/search') && !href.includes('/groups/')) {{
                        seen.add(text);
                        results.push({{
                            name: text,
                            profile_url: href,
                            source: 'facebook_search',
                            company: '',
                            phone: '',
                            email: '',
                        }});
                    }}
                }}
                if (results.length >= {max_results}) break;
            }}
            return results;
        }})()
        """
        try:
            data = await self._evaluate(js)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []


# ============================================================
# 高级流程：完整获客工作流
# ============================================================

async def find_customers(
    query: str,
    search_type: str = "all",
    max_results: int = 20,
    headless: bool = False,  # OpenCLI 版忽略此参数
    fb_email: str = "",
    fb_password: str = "",
) -> dict:
    """
    完整获客流程（与 browser_agent.py 接口一致）:
    1. 连接 OpenCLI（用户已登录的 Chrome）
    2. 搜索目标关键词
    3. 提取潜在客户信息
    4. AI 分析评分
    5. 返回结果
    """
    fb = FacebookBrowser()
    result = {"success": False, "profiles": [], "groups": [], "message": ""}

    try:
        await fb.start()

        # 检查登录状态
        logged_in = await fb.is_logged_in()
        if not logged_in:
            result["message"] = (
                "Chrome 未登录 Facebook。请在 Chrome 浏览器中手动登录 Facebook，"
                "登录后再试。（OpenCLI 模式会直接复用 Chrome 的登录状态）"
            )
            return result

        all_profiles = []

        if search_type in ("people", "all"):
            people = await fb.search_people(query, max_results)
            all_profiles.extend(people)

        if search_type in ("pages", "all"):
            pages = await fb.search_pages(query, max_results)
            all_profiles.extend(pages)

        groups = []
        if search_type in ("groups", "all"):
            groups = await fb.search_groups(query, 10)
            result["groups"] = groups

        # 去重
        seen_names = set()
        unique_profiles = []
        for p in all_profiles:
            name = p.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                unique_profiles.append(p)

        # AI 分析
        if unique_profiles:
            unique_profiles = await ai_analyze_profiles(unique_profiles, query)
            unique_profiles.sort(key=lambda x: x.get("score", 0), reverse=True)

        result["profiles"] = unique_profiles[:max_results]
        result["success"] = True
        result["message"] = (
            f"搜索完成（OpenCLI 模式）。找到 {len(unique_profiles)} 个潜在客户"
            + (f"，{len(groups)} 个相关群组" if groups else "")
            + "。"
        )

    except Exception as e:
        result["message"] = f"搜索出错: {str(e)}"
        logger.error(f"find_customers (opencli) failed: {e}", exc_info=True)
    finally:
        await fb.close()

    return result


# ============================================================
# 可用性检测
# ============================================================

async def is_opencli_ready() -> bool:
    """检查 OpenCLI 是否可用（已安装 + daemon 可连接 + 扩展已连接）。"""
    if not _opencli_available():
        return False
    status = await _daemon_status()
    return status.get("ok", False) and status.get("extensionConnected", False)


# ============================================================
# CLI 测试入口
# ============================================================

if __name__ == "__main__":
    import sys

    async def main():
        print("Checking OpenCLI status...")
        ready = await is_opencli_ready()
        print(f"OpenCLI ready: {ready}")

        if not ready:
            print("OpenCLI not ready. Make sure:")
            print("  1. npm install -g @jackwener/opencli")
            print("  2. Chrome extension installed")
            print("  3. Chrome is running")
            return

        query = " ".join(sys.argv[1:]) or "electronics buyer Southeast Asia"
        print(f"\nSearching Facebook for: {query}")

        result = await find_customers(query)
        print(f"\nStatus: {'OK' if result['success'] else 'FAIL'}")
        print(f"Message: {result['message']}")

        if result["profiles"]:
            print(f"\nFound {len(result['profiles'])} profiles:")
            for i, p in enumerate(result["profiles"], 1):
                score = p.get("score", "?")
                print(f"  {i}. {p['name']} | {p.get('company', '-')} | Score: {score}")

    asyncio.run(main())
