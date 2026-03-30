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

        # Detect if running in a headless environment (Docker / Xvfb)
        display = os.environ.get("DISPLAY", "")
        headless = not bool(display)

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
    ) -> list[dict]:
        """Search Facebook for people matching the given criteria."""
        if not self._page:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")

        page = self._page
        results: list[dict] = []

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

            await _human_scroll(page, times=4)
            await _random_delay(2, 4)

            result_links = await page.query_selector_all(
                'div[role="article"] a[role="presentation"], '
                'div[data-pagelet*="SearchResult"] a[href*="/profile.php"], '
                'div[data-pagelet*="SearchResult"] a[href*="facebook.com/"]'
            )

            seen_urls: set[str] = set()

            for link in result_links[:30]:
                try:
                    href = await link.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue
                    if "/profile.php" not in href and "facebook.com/" not in href:
                        continue
                    if "/search/" in href or "/hashtag/" in href:
                        continue

                    seen_urls.add(href)

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

                    platform_user_id = ""
                    if "profile.php?id=" in href:
                        platform_user_id = href.split("id=")[1].split("&")[0]
                    else:
                        parts = href.rstrip("/").split("/")
                        platform_user_id = parts[-1] if parts else ""

                    if name:
                        results.append({
                            "platform_user_id": platform_user_id,
                            "name": name,
                            "profile_url": href.split("?")[0] if "profile.php" not in href else href,
                            "snippet": snippet,
                        })

                except Exception as e:
                    logger.debug("Failed to parse a search result: %s", e)
                    continue

            logger.info("search_people: found %d results for '%s'", len(results), query)

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

    # -- Messaging -----------------------------------------------------------

    async def send_message(self, profile_url: str, message: str) -> bool:
        """Send a direct message to a Facebook user."""
        if not self._page:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")

        page = self._page

        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(3, 5)
            await _random_mouse_move(page)

            message_btn = await page.query_selector(
                'div[aria-label="Message"], '
                'div[aria-label="发消息"], '
                'a[aria-label="Message"], '
                'a[aria-label="发消息"], '
                'div[role="button"]:has-text("Message"), '
                'div[role="button"]:has-text("发消息")'
            )
            if not message_btn:
                logger.error("send_message: Message button not found on %s", profile_url)
                await _save_screenshot(page, "no_message_btn")
                return False

            await message_btn.click()
            await _random_delay(2, 4)

            msg_input = await page.wait_for_selector(
                'div[role="textbox"][contenteditable="true"], '
                'div[aria-label*="message" i][contenteditable="true"], '
                'div[aria-label*="消息"][contenteditable="true"]',
                timeout=10000,
            )
            if not msg_input:
                logger.error("send_message: Message input not found")
                await _save_screenshot(page, "no_msg_input")
                return False

            await msg_input.click()
            await _random_delay(0.5, 1.0)
            for char in message:
                await page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.05, 0.15))

            await _random_delay(1, 2)

            await page.keyboard.press("Enter")
            await _random_delay(2, 3)

            logger.info("send_message: message sent to %s (%d chars)", profile_url, len(message))
            return True

        except Exception as e:
            logger.error("send_message failed for %s: %s", profile_url, e)
            await _save_screenshot(page, "send_error")
            return False

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
