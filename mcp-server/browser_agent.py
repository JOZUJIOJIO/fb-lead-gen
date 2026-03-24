"""
Facebook 浏览器自动化 Agent

通过 Playwright 控制浏览器，在 Facebook 上搜索潜在客户，
提取信息后导入 LeadFlow 系统。

流程:
1. 启动浏览器（使用已保存的 Facebook 登录状态）
2. 在 Facebook 搜索目标关键词
3. 浏览搜索结果（People / Pages / Groups）
4. 提取潜在客户信息
5. 用 AI 初步筛选
6. 返回结果列表
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

# Facebook 登录状态保存目录
FB_STATE_DIR = Path.home() / ".leadflow" / "fb-state"
FB_STATE_DIR.mkdir(parents=True, exist_ok=True)
FB_STATE_FILE = FB_STATE_DIR / "state.json"

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-k2.5")


# ============================================================
# AI 辅助：用 Kimi 分析页面内容
# ============================================================

async def ai_analyze_profiles(profiles: list[dict], search_context: str) -> list[dict]:
    """用 AI 分析提取到的 profile 数据，判断是否为潜在买家。"""
    if not KIMI_API_KEY or not profiles:
        return profiles

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
                f"{KIMI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {KIMI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": KIMI_MODEL,
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

            # 合并回原始数据
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
# Facebook 浏览器操作
# ============================================================

class FacebookBrowser:
    """控制浏览器在 Facebook 上搜索客户。"""

    def __init__(self):
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.playwright = None

    async def start(self, headless: bool = False):
        """启动浏览器，使用 persistent context 保持 Facebook 登录状态。

        注意：Facebook 会检测 headless 模式并阻止登录，所以始终用有头模式。
        """
        self.playwright = await async_playwright().start()
        chrome_data = FB_STATE_DIR / "chrome-data"
        chrome_data.mkdir(parents=True, exist_ok=True)

        context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(chrome_data),
            headless=False,  # Facebook 不允许 headless
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            viewport={"width": 1280, "height": 900},
        )
        self.page = context.pages[0] if context.pages else await context.new_page()
        self.browser = None
        self._context = context

        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

    async def close(self):
        try:
            if hasattr(self, '_context') and self._context:
                await self._context.close()
            elif self.browser:
                await self.browser.close()
        except Exception:
            pass
        if self.playwright:
            await self.playwright.stop()

    async def is_logged_in(self) -> bool:
        """检查是否已登录 Facebook。"""
        try:
            await self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=15000)
            await self.page.wait_for_timeout(2000)
            # 检查是否有搜索栏（已登录的标志）
            search = await self.page.query_selector('[aria-label="Search Facebook"]')
            return search is not None
        except Exception:
            return False

    async def login(self, email: str, password: str) -> bool:
        """登录 Facebook。首次使用时需要调用。"""
        try:
            await self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000)

            # 填写登录表单
            await self.page.fill('[name="email"]', email)
            await self.page.fill('[name="pass"]', password)
            await self.page.click('[name="login"]')
            await self.page.wait_for_timeout(5000)

            # 检查是否需要两步验证（如果有的话用户需要手动处理）
            logged_in = await self.is_logged_in()
            if logged_in:
                # 保存登录状态
                storage = await self.page.context.storage_state()
                FB_STATE_FILE.write_text(json.dumps(storage))
                logger.info("Facebook login successful, state saved.")
            return logged_in
        except Exception as e:
            logger.error(f"Facebook login failed: {e}")
            return False

    async def search_people(self, query: str, max_results: int = 20) -> list[dict]:
        """在 Facebook 上搜索 People，提取资料信息。"""
        results = []
        try:
            # 导航到搜索页面
            search_url = f"https://www.facebook.com/search/people/?q={query}"
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await self.page.wait_for_timeout(3000)

            # 滚动加载更多结果
            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await self.page.wait_for_timeout(1500)

            # 提取搜索结果
            # Facebook 搜索结果的结构是动态的，用通用选择器
            cards = await self.page.query_selector_all('[role="article"], [data-visualcompletion="ignore-dynamic"]')

            for card in cards[:max_results]:
                try:
                    profile = await self._extract_person_card(card)
                    if profile and profile.get("name"):
                        results.append(profile)
                except Exception:
                    continue

            # 如果通用选择器没抓到，尝试从页面文本提取
            if not results:
                results = await self._extract_from_page_text(query)

        except Exception as e:
            logger.error(f"Facebook search failed: {e}")

        return results

    async def search_pages(self, query: str, max_results: int = 20) -> list[dict]:
        """在 Facebook 上搜索 Pages（公司/品牌页面）。"""
        results = []
        try:
            search_url = f"https://www.facebook.com/search/pages/?q={query}"
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await self.page.wait_for_timeout(3000)

            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await self.page.wait_for_timeout(1500)

            # 提取页面链接和名称
            links = await self.page.query_selector_all('a[href*="facebook.com/"]')
            seen = set()
            for link in links:
                try:
                    href = await link.get_attribute("href") or ""
                    text = (await link.inner_text()).strip()
                    if not text or len(text) < 2 or len(text) > 100:
                        continue
                    if text in seen or "facebook.com/search" in href:
                        continue
                    if any(skip in text.lower() for skip in ["log in", "sign up", "facebook", "people", "photos", "videos", "posts", "groups"]):
                        continue

                    seen.add(text)
                    results.append({
                        "name": text,
                        "company": text,
                        "profile_url": href,
                        "source": "facebook_page_search",
                        "phone": "",
                        "email": "",
                    })
                    if len(results) >= max_results:
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Facebook page search failed: {e}")

        return results

    async def search_groups(self, query: str, max_results: int = 10) -> list[dict]:
        """在 Facebook 上搜索 Groups，找到相关行业群组。"""
        results = []
        try:
            search_url = f"https://www.facebook.com/search/groups/?q={query}"
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await self.page.wait_for_timeout(3000)

            links = await self.page.query_selector_all('a[href*="/groups/"]')
            seen = set()
            for link in links:
                try:
                    href = await link.get_attribute("href") or ""
                    text = (await link.inner_text()).strip()
                    if not text or len(text) < 3 or text in seen:
                        continue
                    if "search" in href or "groups/?q" in href:
                        continue

                    seen.add(text)
                    results.append({
                        "name": text,
                        "group_url": href,
                        "type": "group",
                    })
                    if len(results) >= max_results:
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Facebook group search failed: {e}")

        return results

    async def extract_group_members(self, group_url: str, max_members: int = 20) -> list[dict]:
        """进入一个 Facebook Group，提取活跃成员信息。"""
        results = []
        try:
            # 去群组的 members 页面
            members_url = group_url.rstrip("/") + "/members"
            await self.page.goto(members_url, wait_until="domcontentloaded", timeout=20000)
            await self.page.wait_for_timeout(3000)

            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await self.page.wait_for_timeout(1500)

            # 提取成员链接
            links = await self.page.query_selector_all('a[href*="facebook.com/"]')
            seen = set()
            for link in links:
                try:
                    href = await link.get_attribute("href") or ""
                    text = (await link.inner_text()).strip()
                    if not text or len(text) < 2 or len(text) > 60 or text in seen:
                        continue
                    if any(skip in href for skip in ["/groups/", "/search", "?__cft__"]):
                        continue

                    seen.add(text)
                    results.append({
                        "name": text,
                        "profile_url": href,
                        "source": "facebook_group",
                        "company": "",
                        "phone": "",
                        "email": "",
                    })
                    if len(results) >= max_members:
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Group member extraction failed: {e}")

        return results

    async def visit_profile(self, profile_url: str) -> dict:
        """访问一个用户的 Profile 页面，提取详细信息。"""
        info = {"profile_url": profile_url}
        try:
            # 访问 About 页面获取更多信息
            about_url = profile_url.rstrip("/") + "/about"
            await self.page.goto(about_url, wait_until="domcontentloaded", timeout=15000)
            await self.page.wait_for_timeout(2000)

            # 提取页面文本
            body_text = await self.page.inner_text("body")

            # 尝试提取名字（通常是页面标题的一部分）
            title = await self.page.title()
            if title and "|" in title:
                info["name"] = title.split("|")[0].strip()
            elif title:
                info["name"] = title.replace(" | Facebook", "").strip()

            # 提取工作信息
            work_patterns = [
                r"Works? at (.+?)(?:\n|$)",
                r"(?:CEO|Founder|Manager|Director|Owner) (?:at|of) (.+?)(?:\n|$)",
            ]
            for pattern in work_patterns:
                match = re.search(pattern, body_text, re.IGNORECASE)
                if match:
                    info["company"] = match.group(1).strip()
                    break

            # 提取位置
            location_match = re.search(r"Lives in (.+?)(?:\n|$)", body_text, re.IGNORECASE)
            if location_match:
                info["location"] = location_match.group(1).strip()

            # 提取简介
            bio_match = re.search(r"Bio\n(.+?)(?:\n|$)", body_text)
            if bio_match:
                info["bio"] = bio_match.group(1).strip()

            # 提取电话（如果公开）
            phone_match = re.search(r"(\+?\d[\d\s\-]{8,15})", body_text)
            if phone_match:
                info["phone"] = phone_match.group(1).strip()

            # 提取邮箱（如果公开）
            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", body_text)
            if email_match:
                info["email"] = email_match.group(0)

        except Exception as e:
            logger.error(f"Profile extraction failed: {e}")

        return info

    async def send_dm(self, profile_url: str, message: str) -> bool:
        """给一个 Facebook 用户发送私信 (Direct Message)。

        流程：打开用户主页 → 点击 Message 按钮 → 输入消息 → 发送
        """
        try:
            await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
            await self.page.wait_for_timeout(2000)

            # 找到 Message 按钮并点击
            msg_btn = await self.page.query_selector(
                'a[href*="/messages/"], [aria-label*="Message"], [aria-label*="message"]'
            )
            if not msg_btn:
                # 备用: 直接构造 Messenger URL
                # 从 profile URL 提取用户名或ID
                username = profile_url.rstrip("/").split("/")[-1]
                messenger_url = f"https://www.facebook.com/messages/t/{username}"
                await self.page.goto(messenger_url, wait_until="domcontentloaded", timeout=15000)
                await self.page.wait_for_timeout(3000)
            else:
                await msg_btn.click()
                await self.page.wait_for_timeout(3000)

            # 找到消息输入框
            input_box = await self.page.query_selector(
                '[aria-label*="Message"], [aria-label*="message"], '
                '[role="textbox"], div[contenteditable="true"]'
            )
            if not input_box:
                logger.error("Could not find message input box")
                return False

            # 输入消息
            await input_box.click()
            await self.page.wait_for_timeout(500)

            # 逐行输入（处理多行消息）
            for line in message.split("\n"):
                await self.page.keyboard.type(line, delay=30)
                await self.page.keyboard.press("Shift+Enter")

            await self.page.wait_for_timeout(500)

            # 发送消息（按 Enter）
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(2000)

            logger.info(f"DM sent to {profile_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to send DM to {profile_url}: {e}")
            return False

    async def read_latest_replies(self, profile_url: str, since_count: int = 5) -> list[dict]:
        """读取与某用户的最新消息（检查是否有回复）。

        返回最近的消息列表，包含发送方标识。
        """
        replies = []
        try:
            username = profile_url.rstrip("/").split("/")[-1]
            messenger_url = f"https://www.facebook.com/messages/t/{username}"
            await self.page.goto(messenger_url, wait_until="domcontentloaded", timeout=15000)
            await self.page.wait_for_timeout(3000)

            # 获取消息气泡
            msg_rows = await self.page.query_selector_all('[role="row"], [data-scope="messages_table"]')
            if not msg_rows:
                # 备用选择器
                msg_rows = await self.page.query_selector_all('div[class*="message"]')

            for row in msg_rows[-since_count:]:
                try:
                    text = (await row.inner_text()).strip()
                    if not text or len(text) < 1:
                        continue
                    # 判断是自己发的还是对方发的（通过样式/位置）
                    # Facebook 自己发的消息通常有蓝色背景
                    class_name = await row.get_attribute("class") or ""
                    is_ours = "blue" in class_name.lower() or "outgoing" in class_name.lower()

                    replies.append({
                        "role": "us" if is_ours else "them",
                        "content": text,
                    })
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Failed to read replies from {profile_url}: {e}")

        return replies

    async def check_unread_messages(self) -> list[dict]:
        """检查 Facebook Messenger 中的未读消息。"""
        unread = []
        try:
            await self.page.goto("https://www.facebook.com/messages/", wait_until="domcontentloaded", timeout=15000)
            await self.page.wait_for_timeout(3000)

            # 查找有未读标记的对话
            threads = await self.page.query_selector_all('a[href*="/messages/t/"]')
            for thread in threads[:20]:
                try:
                    text = (await thread.inner_text()).strip()
                    href = await thread.get_attribute("href") or ""
                    # 检查是否有未读标记（通常是加粗文本或特殊样式）
                    parent = await thread.query_selector("..")
                    if parent:
                        style = await parent.get_attribute("class") or ""
                        if "unread" in style.lower() or "bold" in style.lower():
                            unread.append({
                                "thread_url": href,
                                "preview": text[:100],
                            })
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Failed to check unread messages: {e}")

        return unread

    async def _extract_person_card(self, card) -> dict | None:
        """从一个搜索结果卡片中提取人物信息。"""
        try:
            text = await card.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if not lines:
                return None

            # 尝试获取链接
            link = await card.query_selector("a[href*='facebook.com/']")
            profile_url = ""
            if link:
                profile_url = await link.get_attribute("href") or ""

            name = lines[0] if lines else ""
            company = ""
            bio = ""

            for line in lines[1:]:
                if any(kw in line.lower() for kw in ["works at", "ceo", "founder", "manager", "director", "owner"]):
                    company = line
                elif len(line) > 10:
                    bio = line
                    break

            return {
                "name": name,
                "company": company,
                "bio": bio,
                "profile_url": profile_url,
                "source": "facebook_people_search",
                "phone": "",
                "email": "",
            }
        except Exception:
            return None

    async def _extract_from_page_text(self, query: str) -> list[dict]:
        """备用方案：从页面完整文本中提取信息。"""
        results = []
        try:
            body_text = await self.page.inner_text("body")
            # 简单的基于文本的提取
            links = await self.page.query_selector_all('a[role="presentation"], a[href*="facebook.com/"]')
            seen = set()
            for link in links:
                text = (await link.inner_text()).strip()
                href = await link.get_attribute("href") or ""
                if text and len(text) > 2 and len(text) < 60 and text not in seen:
                    if "facebook.com/search" not in href and "/groups/" not in href:
                        seen.add(text)
                        results.append({
                            "name": text,
                            "profile_url": href,
                            "source": "facebook_search",
                            "company": "",
                            "phone": "",
                            "email": "",
                        })
                if len(results) >= 20:
                    break
        except Exception:
            pass
        return results

    async def take_screenshot(self, filename: str = "screenshot.png"):
        """截图当前页面，用于调试。"""
        path = FB_STATE_DIR / filename
        await self.page.screenshot(path=str(path))
        return str(path)


# ============================================================
# 高级流程：完整的获客工作流
# ============================================================

async def find_customers(
    query: str,
    search_type: str = "all",  # people, pages, groups, all
    max_results: int = 20,
    headless: bool = True,
    fb_email: str = "",
    fb_password: str = "",
) -> dict:
    """
    完整获客流程:
    1. 启动浏览器
    2. 登录 Facebook（或使用已保存状态）
    3. 搜索目标关键词
    4. 提取潜在客户信息
    5. AI 分析评分
    6. 返回结果

    Returns:
        {
            "success": bool,
            "profiles": [...],
            "groups": [...],
            "message": str
        }
    """
    fb = FacebookBrowser()
    result = {"success": False, "profiles": [], "groups": [], "message": ""}

    try:
        await fb.start(headless=headless)

        # 检查登录状态
        logged_in = await fb.is_logged_in()
        if not logged_in:
            if fb_email and fb_password:
                logged_in = await fb.login(fb_email, fb_password)
            if not logged_in:
                result["message"] = (
                    "未登录 Facebook。请先用 login_facebook 工具登录，"
                    "或设置 FB_EMAIL 和 FB_PASSWORD 环境变量。"
                )
                return result

        all_profiles = []

        # 搜索 People
        if search_type in ("people", "all"):
            people = await fb.search_people(query, max_results)
            all_profiles.extend(people)

        # 搜索 Pages
        if search_type in ("pages", "all"):
            pages = await fb.search_pages(query, max_results)
            all_profiles.extend(pages)

        # 搜索 Groups
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
            # 按评分排序
            unique_profiles.sort(key=lambda x: x.get("score", 0), reverse=True)

        result["profiles"] = unique_profiles[:max_results]
        result["success"] = True
        result["message"] = (
            f"搜索完成。找到 {len(unique_profiles)} 个潜在客户"
            + (f"，{len(groups)} 个相关群组" if groups else "")
            + "。"
        )

    except Exception as e:
        result["message"] = f"搜索出错: {str(e)}"
        logger.error(f"find_customers failed: {e}", exc_info=True)
    finally:
        await fb.close()

    return result


# ============================================================
# CLI 测试入口
# ============================================================

if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) or "electronics buyer Southeast Asia"
    print(f"🔍 Searching Facebook for: {query}")

    result = asyncio.run(find_customers(query, headless=False))

    print(f"\n{'='*60}")
    print(f"Status: {'✅' if result['success'] else '❌'}")
    print(f"Message: {result['message']}")

    if result["profiles"]:
        print(f"\n📋 Found {len(result['profiles'])} profiles:")
        for i, p in enumerate(result["profiles"], 1):
            score = p.get("score", "?")
            print(f"  {i}. {p['name']} | {p.get('company', '-')} | Score: {score}")
            if p.get("ai_reason"):
                print(f"     → {p['ai_reason']}")

    if result["groups"]:
        print(f"\n👥 Found {len(result['groups'])} groups:")
        for g in result["groups"]:
            print(f"  • {g['name']}")
