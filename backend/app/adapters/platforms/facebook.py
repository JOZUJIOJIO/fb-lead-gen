"""Facebook platform adapter using Patchright for browser automation."""

import asyncio
import json as _json
import logging
import os
import random
import shutil
import string
from datetime import datetime
from pathlib import Path

from patchright.async_api import async_playwright, Page, BrowserContext

from app.adapters.base import PlatformAdapter
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BROWSER_DATA_DIR = "/tmp/leadflow-browser/facebook"
SCREENSHOT_DIR = "/tmp/leadflow-browser/screenshots"
COOKIES_FILE = "/tmp/leadflow-browser/facebook_cookies.json"
LOCK_FILE = os.path.join(BROWSER_DATA_DIR, "SingletonLock")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_browser_locks():
    """Remove stale lock files that prevent browser from starting."""
    for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lock_path = os.path.join(BROWSER_DATA_DIR, lock_name)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
                logger.info("Removed stale lock file: %s", lock_path)
            except OSError as e:
                logger.warning("Failed to remove lock file %s: %s", lock_path, e)


async def _random_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Sleep for a random duration to mimic human behavior."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _human_type(page: Page, selector: str, text: str) -> None:
    """Type text character-by-character with random delays like a human."""
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.15))


async def _human_scroll(page: Page, times: int = 3) -> None:
    """Scroll the page like a human — variable distances and pauses."""
    for _ in range(times):
        distance = random.randint(300, 700)
        await page.mouse.wheel(0, distance)
        await asyncio.sleep(random.uniform(0.8, 2.0))


async def _random_mouse_move(page: Page) -> None:
    """Move the mouse to a random position to appear human."""
    x = random.randint(100, 1200)
    y = random.randint(100, 700)
    await page.mouse.move(x, y)
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def _save_screenshot(page: Page, label: str) -> str:
    """Save a screenshot for debugging. Returns the file path."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    path = os.path.join(SCREENSHOT_DIR, f"{label}_{ts}_{rand}.png")
    await page.screenshot(path=path)
    logger.info("Screenshot saved: %s", path)
    return path


# ---------------------------------------------------------------------------
# Facebook Adapter
# ---------------------------------------------------------------------------

class FacebookAdapter(PlatformAdapter):
    """Facebook automation adapter powered by Patchright (Chromium)."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # -- Lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        """Launch browser with anti-detection settings and persistent session.

        Handles stale lock files from previous unclean shutdowns and falls back
        to a fresh profile if persistent context is corrupted.
        """
        os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

        # Clear stale lock files from previous crashes
        _clear_browser_locks()

        self._playwright = await async_playwright().start()

        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
        ]
        if settings.PROXY_SERVER:
            launch_args.append(f"--proxy-server={settings.PROXY_SERVER}")

        # Force headless in Docker (/.dockerenv exists) or when no real display
        in_docker = os.path.exists("/.dockerenv")
        display = os.environ.get("DISPLAY", "")
        headless = in_docker or not bool(display)

        # Try persistent context; if corrupted, nuke and retry
        for attempt in range(2):
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=BROWSER_DATA_DIR,
                    headless=headless,
                    args=launch_args,
                    viewport=viewport,
                    user_agent=user_agent,
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    ignore_https_errors=True,
                )
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(
                        "Persistent context failed (%s), clearing profile and retrying...", e,
                    )
                    _clear_browser_locks()
                    # Nuke the corrupted profile
                    try:
                        shutil.rmtree(BROWSER_DATA_DIR, ignore_errors=True)
                        os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
                    except Exception:
                        pass
                else:
                    raise

        # Load saved cookies if available
        if os.path.exists(COOKIES_FILE):
            try:
                cookies = _json.loads(Path(COOKIES_FILE).read_text())
                if cookies:
                    await self._context.add_cookies(cookies)
                    logger.info("Loaded %d cookies from %s", len(cookies), COOKIES_FILE)
            except Exception as e:
                logger.warning("Failed to load cookies: %s", e)

        # Reuse existing page or create one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        logger.info(
            "Facebook adapter initialized (headless=%s, viewport=%s, ua=%s...)",
            headless, viewport, user_agent[:40],
        )

    # -- Search --------------------------------------------------------------

    async def search_people(
        self,
        keywords: str,
        region: str = "",
        industry: str = "",
        known_uids: set[str] | None = None,
        target_new: int = 20,
    ) -> list[dict]:
        """Search Facebook for people matching the given criteria.

        Args:
            known_uids: UIDs to skip (already processed/blacklisted).
            target_new: Keep scrolling until this many NEW people are found
                        (or page has no more results). Max 10 scroll rounds.
        """
        if not self._page:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")

        page = self._page
        results: list[dict] = []
        skip_uids = known_uids or set()
        seen_urls: set[str] = set()

        try:
            query_parts = [keywords]
            if region:
                query_parts.append(region)
            if industry:
                query_parts.append(industry)
            query = " ".join(query_parts)

            search_url = f"https://www.facebook.com/search/people/?q={query}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(3, 6)
            await _random_mouse_move(page)

            # Scroll in rounds — keep going until enough new people or no more results
            max_scroll_rounds = 10
            for scroll_round in range(max_scroll_rounds):
                await _human_scroll(page, times=3)
                await _random_delay(2, 4)

                result_links = await page.query_selector_all(
                    'div[role="article"] a[role="presentation"], '
                    'div[data-pagelet*="SearchResult"] a[href*="/profile.php"], '
                    'div[data-pagelet*="SearchResult"] a[href*="facebook.com/"]'
                )

                new_in_round = 0
                for link in result_links:
                    try:
                        href = await link.get_attribute("href") or ""
                        if not href or href in seen_urls:
                            continue
                        if "/profile.php" not in href and "facebook.com/" not in href:
                            continue
                        if "/search/" in href or "/hashtag/" in href:
                            continue

                        seen_urls.add(href)

                        platform_user_id = ""
                        if "profile.php?id=" in href:
                            platform_user_id = href.split("id=")[1].split("&")[0]
                        else:
                            parts = href.rstrip("/").split("/")
                            platform_user_id = parts[-1] if parts else ""

                        # Skip already known UIDs
                        if platform_user_id and platform_user_id in skip_uids:
                            continue

                        name = (await link.inner_text()).strip()
                        if not name:
                            name_el = await link.query_selector("span")
                            if name_el:
                                name = (await name_el.inner_text()).strip()

                        parent = await link.evaluate_handle("el => el.closest('div[role=\"article\"]') || el.parentElement.parentElement")
                        snippet = ""
                        try:
                            snippet_text = await parent.evaluate("el => el.innerText")
                            if name and name in snippet_text:
                                snippet = snippet_text.split(name, 1)[-1].strip()[:200]
                            else:
                                snippet = snippet_text[:200]
                        except Exception:
                            pass

                        if name:
                            results.append({
                                "platform_user_id": platform_user_id,
                                "name": name,
                                "profile_url": href.split("?")[0] if "profile.php" not in href else href,
                                "snippet": snippet,
                            })
                            new_in_round += 1

                    except Exception as e:
                        logger.debug("Failed to parse a search result: %s", e)
                        continue

                new_count = len(results)
                logger.info(
                    "search_people: round %d/%d — %d new this round, %d total new for '%s'",
                    scroll_round + 1, max_scroll_rounds, new_in_round, new_count, query,
                )

                # Stop if we have enough new people
                if new_count >= target_new:
                    break

                # Stop if no new results in this round (reached bottom)
                if new_in_round == 0:
                    logger.info("search_people: no new results in round %d, stopping scroll", scroll_round + 1)
                    break

            logger.info("search_people: found %d new results for '%s'", len(results), query)

        except Exception as e:
            logger.error("search_people failed: %s", e)
            await _save_screenshot(page, "search_error")

        return results

    # -- Profile -------------------------------------------------------------

    async def get_profile(self, profile_url: str) -> dict:
        """Navigate to a profile and extract structured data."""
        if not self._page:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")

        page = self._page
        profile_data: dict = {"profile_url": profile_url, "raw_html": ""}

        try:
            about_url = profile_url.rstrip("/") + "/about"
            await page.goto(about_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(3, 5)
            await _random_mouse_move(page)
            await _human_scroll(page, times=2)

            name_el = await page.query_selector("h1")
            if name_el:
                profile_data["name"] = (await name_el.inner_text()).strip()

            intro_section = await page.query_selector(
                'div[data-pagelet="ProfileTileCollection"], '
                'div[data-pagelet="ProfileAppSection_0"]'
            )
            if intro_section:
                profile_data["bio"] = (await intro_section.inner_text()).strip()[:500]

            about_items = await page.query_selector_all(
                'div[data-pagelet*="about"] span, '
                'div[data-pagelet*="ProfileAppSection"] span'
            )
            work_texts: list[str] = []
            edu_texts: list[str] = []
            location_text = ""
            for item in about_items[:50]:
                try:
                    text = (await item.inner_text()).strip()
                    lower = text.lower()
                    if any(kw in lower for kw in ["works at", "worked at", "在", "工作"]):
                        work_texts.append(text)
                    elif any(kw in lower for kw in ["studied at", "goes to", "学习", "毕业"]):
                        edu_texts.append(text)
                    elif any(kw in lower for kw in ["lives in", "from", "住在", "来自"]):
                        location_text = text
                except Exception:
                    continue

            profile_data["work"] = "; ".join(work_texts[:3]) if work_texts else ""
            profile_data["education"] = "; ".join(edu_texts[:3]) if edu_texts else ""
            profile_data["location"] = location_text

            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(2, 4)
            await _human_scroll(page, times=3)

            post_elements = await page.query_selector_all(
                'div[data-pagelet*="ProfileTimeline"] div[dir="auto"], '
                'div[role="article"] div[dir="auto"]'
            )
            recent_posts: list[str] = []
            for post_el in post_elements[:10]:
                try:
                    text = (await post_el.inner_text()).strip()
                    if len(text) > 20:
                        recent_posts.append(text[:300])
                        if len(recent_posts) >= 5:
                            break
                except Exception:
                    continue
            profile_data["recent_posts"] = recent_posts

            profile_data["raw_html"] = await page.content()

            logger.info("get_profile: extracted profile for '%s'", profile_data.get("name", "unknown"))

        except Exception as e:
            logger.error("get_profile failed for %s: %s", profile_url, e)
            await _save_screenshot(page, "profile_error")

        return profile_data

    # -- Pre-check: can we message this user? --------------------------------

    async def check_can_message(self, profile_url: str) -> dict:
        """Check if the profile has a Message button, without clicking it.

        Returns {"ok": True} or {"ok": False, "code": str, "reason": str}.
        Assumes the page is already on the profile (from get_profile).
        """
        if not self._page:
            return {"ok": False, "code": "adapter_not_ready", "reason": "浏览器未初始化"}

        page = self._page

        # Make sure we're on the profile page (get_profile may have left us on timeline)
        current_url = page.url or ""
        if profile_url.rstrip("/") not in current_url:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(2, 3)

        try:
            # Check for Message button via selectors
            for sel in self._MSG_BTN_SELECTORS:
                btn = await page.query_selector(sel)
                if btn:
                    return {"ok": True}

            # JS fallback: check by aria-label or SVG
            has_btn = await page.evaluate("""() => {
                // Check aria-labels
                const buttons = document.querySelectorAll('[role="button"]');
                for (const btn of buttons) {
                    const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                    if (label.includes('message') || label.includes('消息') || label.includes('发消息'))
                        return true;
                }
                // Check for Messenger SVG
                const svgs = document.querySelectorAll('svg');
                for (const svg of svgs) {
                    const path = svg.querySelector('path');
                    if (path) {
                        const d = path.getAttribute('d') || '';
                        if (d.includes('M12') && (d.includes('C5.37') || d.includes('c-4.97'))) {
                            if (svg.closest('[role="button"], a, button')) return true;
                        }
                    }
                }
                return false;
            }""")

            if has_btn:
                return {"ok": True}

            return {
                "ok": False,
                "code": "no_message_button",
                "reason": "用户主页无「发消息」按钮",
            }

        except Exception as e:
            logger.debug("check_can_message error: %s", e)
            return {"ok": False, "code": "check_error", "reason": f"检查失败: {e}"}

    # -- Messaging -----------------------------------------------------------

    # Wide selector lists for Facebook's many UI variants
    _MSG_BTN_SELECTORS = [
        # Profile page button (en / zh)
        'div[aria-label="Message"]',
        'div[aria-label="发消息"]',
        'a[aria-label="Message"]',
        'a[aria-label="发消息"]',
        # Role-based
        'div[role="button"]:has-text("Message")',
        'div[role="button"]:has-text("发消息")',
        # Link-based (some profiles)
        'a[href*="/messages/t/"]',
        'a[href*="messenger.com"]',
    ]

    _INPUT_SELECTORS = [
        # Chat popup / overlay
        'div[role="textbox"][contenteditable="true"]',
        # Aria-label variants (en / zh, case insensitive via multiple entries)
        'div[aria-label*="message" i][contenteditable="true"]',
        'div[aria-label*="消息"][contenteditable="true"]',
        'div[aria-label*="Aa"][contenteditable="true"]',
        # Messenger full page
        'div[data-lexical-editor="true"][contenteditable="true"]',
        # Generic contenteditable inside chat containers
        'div[role="main"] div[contenteditable="true"]',
        # Paragraph-based editor (new Facebook)
        'p[data-lexical-text="true"]',
    ]

    async def send_message(self, profile_url: str, message: str) -> dict:
        """Send a direct message via Facebook Messenger.

        PRIMARY PATH: Navigate directly to /messages/t/{uid} — avoids profile
        page button confusion (评论框 vs 私信框).

        Returns {"success": bool, "failure_code": str|None}
        """
        if not self._page:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")

        page = self._page

        try:
            # ---- Step 1: Go to Messenger directly ----
            messenger_url = await self._get_messenger_url(page, profile_url)
            if not messenger_url:
                logger.error("send_message: cannot build Messenger URL from %s", profile_url)
                return {"success": False, "failure_code": "message_button_not_found"}

            logger.info("send_message: navigating to Messenger %s", messenger_url)
            await page.goto(messenger_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(4, 6)

            # ---- Step 2-4: Dismiss dialogs + find input (up to 3 attempts) ----
            msg_input = None
            for attempt in range(3):
                await self._dismiss_blocking_dialogs(page)
                await _random_delay(1, 2)

                # Check for platform restrictions
                restriction = await self._detect_platform_restriction(page)
                if restriction:
                    logger.warning("send_message: restriction on %s: %s", profile_url, restriction)
                    await _save_screenshot(page, "platform_restricted")
                    return {"success": False, "failure_code": restriction}

                msg_input = await self._find_messenger_input(page)
                if msg_input:
                    break

                # Diagnostic: log what's actually on the page
                if attempt == 0:
                    diag = await self._diagnose_messenger_page(page)
                    logger.warning("send_message: page diagnosis — %s", diag)

                logger.info(
                    "send_message: input not found (attempt %d/3), trying recovery...",
                    attempt + 1,
                )

                # Recovery: click in the lower area of the page to activate input
                try:
                    viewport = page.viewport_size or {"width": 1280, "height": 720}
                    await page.mouse.click(viewport["width"] // 2, viewport["height"] - 100)
                    await _random_delay(1, 2)
                except Exception:
                    pass

                # Recovery: try pressing Tab to focus input
                try:
                    await page.keyboard.press("Tab")
                    await _random_delay(0.5, 1)
                except Exception:
                    pass

                await _random_delay(2, 4)

            # ---- Step 4b: Last resort — JS-based input discovery ----
            if not msg_input:
                msg_input = await self._find_input_via_js(page)

            if not msg_input:
                logger.error("send_message: input not found on Messenger for %s after all attempts", profile_url)
                await _save_screenshot(page, "no_msg_input")
                return {"success": False, "failure_code": "message_input_not_found"}

            # ---- Step 5: Type and send ----
            await msg_input.click()
            await _random_delay(0.5, 1.0)
            for char in message:
                await page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.05, 0.15))

            await _random_delay(1, 2)
            await page.keyboard.press("Enter")
            await _random_delay(2, 3)

            logger.info("send_message: sent to %s via Messenger (%d chars)", profile_url, len(message))
            return {"success": True, "failure_code": None}

        except Exception as e:
            logger.error("send_message failed for %s: %s", profile_url, e)
            await _save_screenshot(page, "send_error")
            return {"success": False, "failure_code": "send_exception"}

    async def _diagnose_messenger_page(self, page: Page) -> str:
        """Collect diagnostic info about the Messenger page state."""
        try:
            return await page.evaluate("""() => {
                const info = [];
                info.push('URL: ' + location.href);
                info.push('Title: ' + document.title);

                // Count contenteditable elements
                const editables = document.querySelectorAll('[contenteditable="true"]');
                info.push('contenteditable count: ' + editables.length);
                for (let i = 0; i < Math.min(editables.length, 5); i++) {
                    const el = editables[i];
                    const tag = el.tagName;
                    const role = el.getAttribute('role') || '';
                    const label = el.getAttribute('aria-label') || '';
                    const rect = el.getBoundingClientRect();
                    const visible = rect.width > 0 && rect.height > 0;
                    info.push(`  [${i}] ${tag} role="${role}" label="${label}" visible=${visible} ${Math.round(rect.width)}x${Math.round(rect.height)}`);
                }

                // Check for common blocking elements
                const dialogs = document.querySelectorAll('[role="dialog"]');
                info.push('dialogs: ' + dialogs.length);

                // Check for "can't message" indicators
                const bodyText = (document.body.innerText || '').substring(0, 500);
                if (bodyText.includes("can't") || bodyText.includes('无法'))
                    info.push('WARN: page contains "can\\'t" or "无法"');
                if (bodyText.includes('Accept') || bodyText.includes('接受'))
                    info.push('WARN: page contains "Accept" or "接受" (message request?)');

                // Check for textbox role
                const textboxes = document.querySelectorAll('[role="textbox"]');
                info.push('textbox count: ' + textboxes.length);
                for (let i = 0; i < Math.min(textboxes.length, 3); i++) {
                    const el = textboxes[i];
                    const ce = el.getAttribute('contenteditable');
                    const label = el.getAttribute('aria-label') || '';
                    const rect = el.getBoundingClientRect();
                    info.push(`  textbox[${i}] ce="${ce}" label="${label}" ${Math.round(rect.width)}x${Math.round(rect.height)}`);
                }

                return info.join(' | ');
            }""")
        except Exception as e:
            return f"diagnosis failed: {e}"

    async def _find_input_via_js(self, page: Page):
        """Last resort: use JS to find and return the most likely message input."""
        try:
            # Use JS to find the best candidate contenteditable element
            handle = await page.evaluate_handle("""() => {
                // Strategy 1: Find contenteditable with textbox role at bottom of page
                const textboxes = document.querySelectorAll('[role="textbox"][contenteditable="true"]');
                for (const tb of textboxes) {
                    const rect = tb.getBoundingClientRect();
                    // Input should be in the lower half of the viewport and visible
                    if (rect.width > 100 && rect.height > 10 && rect.top > window.innerHeight * 0.3) {
                        return tb;
                    }
                }

                // Strategy 2: Any contenteditable in the lower portion of the page
                const editables = document.querySelectorAll('[contenteditable="true"]');
                let best = null;
                let bestY = 0;
                for (const el of editables) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 10 && rect.top > bestY && rect.top > window.innerHeight * 0.3) {
                        best = el;
                        bestY = rect.top;
                    }
                }
                if (best) return best;

                // Strategy 3: Find by aria-label containing message-related text
                const allEls = document.querySelectorAll('[aria-label]');
                for (const el of allEls) {
                    const label = (el.getAttribute('aria-label') || '').toLowerCase();
                    if ((label.includes('message') || label.includes('消息') || label.includes('type'))
                        && (el.getAttribute('contenteditable') === 'true' || el.querySelector('[contenteditable="true"]'))) {
                        return el.getAttribute('contenteditable') === 'true' ? el : el.querySelector('[contenteditable="true"]');
                    }
                }

                return null;
            }""")

            if handle:
                el = handle.as_element()
                if el:
                    logger.info("send_message: found input via JS fallback")
                    return el
        except Exception as e:
            logger.debug("_find_input_via_js failed: %s", e)

        return None

    async def _find_messenger_input(self, page: Page):
        """Find the message input on the Messenger page (NOT profile page).

        Only matches inputs inside the Messenger conversation area,
        never matches post comment boxes.
        """
        # Messenger-specific selectors (narrowest → broadest)
        messenger_selectors = [
            # Messenger's own input (aria-label contains message/Aa/消息)
            'div[aria-label*="message" i][contenteditable="true"][role="textbox"]',
            'div[aria-label*="消息"][contenteditable="true"][role="textbox"]',
            'div[aria-label*="Aa"][contenteditable="true"][role="textbox"]',
            # Lexical editor on Messenger
            'div[data-lexical-editor="true"][contenteditable="true"][role="textbox"]',
            # Generic textbox but only inside the main messenger area
            'div[role="main"] div[role="textbox"][contenteditable="true"]',
            # Broader fallbacks for newer Messenger layouts
            'div[contenteditable="true"][role="textbox"]',
            'div[role="main"] div[contenteditable="true"]',
        ]

        # First pass: wait for each selector with timeout
        for sel in messenger_selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=4000)
                if el:
                    return el
            except Exception:
                pass

        # Second pass: direct query without waiting
        for sel in messenger_selectors:
            el = await page.query_selector(sel)
            if el:
                return el

        return None

    async def _dismiss_blocking_dialogs(self, page: Page) -> None:
        """Close blocking dialogs like PIN code setup, cookie consent, etc.

        Facebook's dialog close buttons use various patterns:
        - aria-label="Close" / "关闭"
        - SVG X icon inside a clickable div
        - "Not now" / "以后再说" / "继续" text buttons
        """
        try:
            dismissed = await page.evaluate("""() => {
                let closed = 0;

                // Strategy 1: aria-label close buttons (broadened)
                const closeLabels = ['close', '关闭', 'dismiss', '取消', 'not now', '以后再说'];
                const allClickable = document.querySelectorAll('[role="button"], button, [aria-label]');
                for (const el of allClickable) {
                    const label = (el.getAttribute('aria-label') || '').toLowerCase();
                    if (closeLabels.some(l => label.includes(l)) && el.offsetParent !== null) {
                        el.click();
                        closed++;
                    }
                }

                // Strategy 2: Find X icon (svg with close/x path) inside dialogs
                const dialogs = document.querySelectorAll('[role="dialog"]');
                for (const dialog of dialogs) {
                    // Look for small clickable elements near top-right (close buttons)
                    const candidates = dialog.querySelectorAll('div[role="button"], svg, [aria-label]');
                    for (const c of candidates) {
                        const rect = c.getBoundingClientRect();
                        // Close button is typically in top-right quadrant of dialog
                        const dialogRect = dialog.getBoundingClientRect();
                        if (rect.right > dialogRect.right - 80 && rect.top < dialogRect.top + 80) {
                            const clickTarget = c.closest('[role="button"]') || c;
                            if (clickTarget.offsetParent !== null) {
                                clickTarget.click();
                                closed++;
                                break;
                            }
                        }
                    }
                }

                // Strategy 3: Text-based buttons
                const textBtns = document.querySelectorAll('[role="button"], button');
                for (const btn of textBtns) {
                    const text = (btn.textContent || '').trim();
                    if (['Not Now', 'Not now', '以后再说', '稍后', 'Skip', '跳过', '继续'].includes(text)) {
                        if (btn.offsetParent !== null) {
                            btn.click();
                            closed++;
                        }
                    }
                }

                return closed;
            }""")
            if dismissed:
                logger.info("_dismiss_blocking_dialogs: closed %d dialog(s)", dismissed)
                await _random_delay(1, 2)
        except Exception as e:
            logger.debug("_dismiss_blocking_dialogs: %s", e)

    async def _find_message_input(self, page: Page):
        """Search for the message input across the main page and any iframes."""
        combined = ", ".join(self._INPUT_SELECTORS)

        # Try main page first
        try:
            el = await page.wait_for_selector(combined, timeout=6000)
            if el:
                return el
        except Exception:
            pass

        # Try each selector individually (some complex selectors may not combine well)
        for sel in self._INPUT_SELECTORS:
            el = await page.query_selector(sel)
            if el:
                return el

        # Try inside iframes (Messenger popup can be in a frame)
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                el = await frame.query_selector(combined)
                if el:
                    return el
            except Exception:
                continue

        return None

    async def _get_messenger_url(self, page: Page, profile_url: str) -> str | None:
        """Try to construct a Messenger URL from the profile."""
        # Extract user ID or username from profile URL
        if "profile.php?id=" in profile_url:
            uid = profile_url.split("id=")[1].split("&")[0]
        else:
            uid = profile_url.rstrip("/").split("/")[-1]

        if uid:
            return f"https://www.facebook.com/messages/t/{uid}"
        return None

    # Restriction signals: (text_pattern, failure_code)
    _RESTRICTION_SIGNALS = [
        # Identity verification
        ("confirm your identity", "platform_identity_verification"),
        ("确认你的身份", "platform_identity_verification"),
        ("verify your identity", "platform_identity_verification"),
        ("验证你的身份", "platform_identity_verification"),
        # Action restricted / rate limited
        ("actions have been restricted", "platform_action_restricted"),
        ("操作受到限制", "platform_action_restricted"),
        ("action blocked", "platform_action_restricted"),
        ("操作已被屏蔽", "platform_action_restricted"),
        ("you can't use this feature", "platform_feature_blocked"),
        ("你无法使用此功能", "platform_feature_blocked"),
        ("temporarily blocked", "platform_temporarily_blocked"),
        ("暂时被限制", "platform_temporarily_blocked"),
        # Messaging specifically restricted
        ("can't send messages", "platform_messaging_blocked"),
        ("无法发送消息", "platform_messaging_blocked"),
        ("无法发消息", "platform_messaging_blocked"),
        ("你无法发消息给这个账户", "platform_messaging_blocked"),
        ("can't message this", "platform_messaging_blocked"),
        ("unable to send", "platform_messaging_blocked"),
        ("you can't reply", "platform_messaging_blocked"),
        ("你无法回复", "platform_messaging_blocked"),
        # Checkpoint / security
        ("unusual activity", "platform_unusual_activity"),
        ("异常活动", "platform_unusual_activity"),
        ("suspicious activity", "platform_unusual_activity"),
        ("security check", "platform_security_check"),
        ("安全检查", "platform_security_check"),
    ]

    async def _detect_platform_restriction(self, page: Page) -> str | None:
        """Check if Facebook is showing a restriction/identity dialog.

        Scans visible text in dialogs, overlays, and the main page body for
        known restriction patterns. Returns a failure_code string or None.
        """
        try:
            # Check URL first — checkpoint redirects
            url = (page.url or "").lower()
            if "/checkpoint" in url:
                return "platform_checkpoint_redirect"

            # Grab visible text from dialogs AND page body (check both)
            text = await page.evaluate("""() => {
                const parts = [];
                // Collect dialog/overlay text
                const containers = [
                    ...document.querySelectorAll('[role="dialog"]'),
                    ...document.querySelectorAll('[role="alertdialog"]'),
                    ...document.querySelectorAll('[data-testid*="dialog"]'),
                    ...document.querySelectorAll('[class*="overlay"]'),
                    ...document.querySelectorAll('[class*="modal"]'),
                ];
                for (const c of containers) {
                    parts.push(c.innerText || '');
                }
                // Always also check body text
                parts.push((document.body.innerText || '').substring(0, 3000));
                return parts.join(' ');
            }""")

            if not text:
                return None

            text_lower = text.lower()
            for pattern, code in self._RESTRICTION_SIGNALS:
                if pattern in text_lower:
                    return code

        except Exception as e:
            logger.debug("_detect_platform_restriction: evaluation error: %s", e)

        return None

    # -- Inbox scanning (for auto-reply) -------------------------------------

    async def get_unread_threads(self) -> list[dict]:
        """Scan Messenger inbox for threads with unread messages.

        Returns a list of dicts: {"uid": str, "name": str, "thread_url": str}
        """
        if not self._page:
            raise RuntimeError("Adapter not initialized.")

        page = self._page
        results: list[dict] = []

        try:
            await page.goto(
                "https://www.facebook.com/messages/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await _random_delay(3, 5)
            await self._dismiss_blocking_dialogs(page)
            await _random_delay(1, 2)

            # Find unread conversation items — they have a bold/unread indicator
            threads = await page.evaluate("""() => {
                const results = [];
                // Messenger thread rows are links inside the chat list
                const rows = document.querySelectorAll('a[href*="/messages/t/"]');
                for (const row of rows) {
                    const href = row.getAttribute('href') || '';
                    // Unread threads typically have a bold font-weight or an unread dot
                    const parent = row.closest('[role="row"]') || row.parentElement;
                    if (!parent) continue;

                    const style = window.getComputedStyle(parent);
                    const text = parent.innerText || '';

                    // Detect unread: bold text, unread dot, or aria attribute
                    const hasBold = parent.querySelector('span[style*="font-weight"]')
                        || parent.querySelector('strong')
                        || style.fontWeight >= 600;
                    const hasUnreadDot = parent.querySelector('[data-visualcompletion="ignore"]')
                        || parent.querySelector('[aria-label*="unread" i]')
                        || parent.querySelector('[aria-label*="未读"]');

                    if (!hasBold && !hasUnreadDot) continue;

                    // Extract UID from href
                    const match = href.match(/\\/messages\\/t\\/([^/?]+)/);
                    if (!match) continue;
                    const uid = match[1];

                    // Extract name — usually the first line of text
                    const nameEl = parent.querySelector('span[dir="auto"]')
                        || parent.querySelector('span');
                    const name = nameEl ? nameEl.innerText.trim() : '';

                    if (uid && !results.some(r => r.uid === uid)) {
                        results.push({
                            uid: uid,
                            name: name.split('\\n')[0].trim(),
                            thread_url: 'https://www.facebook.com/messages/t/' + uid,
                        });
                    }
                }
                return results;
            }""")

            results = threads or []
            logger.info("get_unread_threads: found %d unread thread(s)", len(results))

        except Exception as e:
            logger.error("get_unread_threads failed: %s", e)
            await _save_screenshot(page, "unread_threads_error")

        return results

    async def read_thread_messages(self, thread_url: str, max_messages: int = 20) -> list[dict]:
        """Read recent messages from a Messenger thread.

        Returns list of {"role": "user"|"assistant", "content": str} where
        "assistant" = our sent messages, "user" = their replies.
        """
        if not self._page:
            raise RuntimeError("Adapter not initialized.")

        page = self._page
        messages: list[dict] = []

        try:
            await page.goto(thread_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(3, 5)
            await self._dismiss_blocking_dialogs(page)
            await _random_delay(1, 2)

            raw_messages = await page.evaluate("""(maxMessages) => {
                const results = [];

                // Step 1: Try to get the logged-in user's name from navigation
                let myName = '';
                // Facebook nav bar profile link or account menu
                const profileLinks = document.querySelectorAll(
                    'a[href*="/profile"], a[aria-label*="个人主页"], a[aria-label*="Profile"]'
                );
                for (const link of profileLinks) {
                    const label = link.getAttribute('aria-label') || '';
                    if (label && !label.includes('Profile') && !label.includes('个人主页')) {
                        myName = label;
                        break;
                    }
                    // Try the text content of nearby elements
                    const nameEl = link.querySelector('span');
                    if (nameEl && nameEl.innerText.trim()) {
                        myName = nameEl.innerText.trim();
                        break;
                    }
                }

                // Step 2: Get viewport width for position-based detection
                const viewportWidth = window.innerWidth;
                const midpoint = viewportWidth / 2;

                // Get all message rows in the conversation
                const messageGroups = document.querySelectorAll('[role="row"]');

                for (const group of messageGroups) {
                    // Determine if this is our message or theirs using multiple strategies

                    const isOurs = (() => {
                        // Strategy 1: Position-based detection (most reliable)
                        // In Messenger, our messages appear on the RIGHT side, theirs on the LEFT
                        const textEls = group.querySelectorAll('div[dir="auto"]');
                        for (const el of textEls) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                // If the message center is in the right half, it's ours
                                const msgCenter = rect.left + rect.width / 2;
                                return msgCenter > midpoint;
                            }
                        }

                        // Strategy 2: Check if sender name matches our name
                        if (myName) {
                            const senderEls = group.querySelectorAll('span[dir="auto"]');
                            for (const el of senderEls) {
                                const name = el.innerText.trim();
                                if (name === myName) return true;
                            }
                        }

                        // Strategy 3: Avatar presence — others' messages have an avatar,
                        // our messages do not show our avatar in Messenger
                        const avatars = group.querySelectorAll('img[alt], svg image');
                        const hasAvatar = avatars.length > 0;
                        if (hasAvatar) return false;

                        return false;
                    })();

                    // Extract message text
                    const textEls = group.querySelectorAll('div[dir="auto"]');
                    for (const el of textEls) {
                        const text = el.innerText.trim();
                        if (text && text.length > 0 && text.length < 5000) {
                            // Skip timestamps, reactions, system messages
                            if (text.match(/^\\d{1,2}:\\d{2}/) || text.match(/^(Yesterday|Today|星期)/))
                                continue;
                            if (text.length < 2) continue;

                            // Deduplicate: skip if same content and role as the last message
                            const lastMsg = results.length > 0 ? results[results.length - 1] : null;
                            if (lastMsg && lastMsg.content === text && lastMsg.role === (isOurs ? 'assistant' : 'user'))
                                continue;

                            results.push({
                                role: isOurs ? 'assistant' : 'user',
                                content: text,
                            });
                        }
                    }

                    if (results.length >= maxMessages) break;
                }

                return results;
            }""", max_messages)

            messages = raw_messages or []
            logger.info(
                "read_thread_messages: read %d message(s) from %s",
                len(messages), thread_url,
            )

        except Exception as e:
            logger.error("read_thread_messages failed for %s: %s", thread_url, e)
            await _save_screenshot(page, "read_thread_error")

        return messages

    # -- Cleanup -------------------------------------------------------------

    async def close(self) -> None:
        """Shut down the browser and playwright instance."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
                self._page = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.info("Facebook adapter closed.")
        except Exception as e:
            logger.error("Error closing Facebook adapter: %s", e)
