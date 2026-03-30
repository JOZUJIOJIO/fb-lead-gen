"""Facebook platform adapter using Patchright for browser automation."""

import asyncio
import logging
import os
import random
import string
from datetime import datetime, timezone
from pathlib import Path

from patchright.async_api import async_playwright, Page, BrowserContext

from adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — Mac-appropriate paths under ~/Library/Application Support
# ---------------------------------------------------------------------------

DATA_DIR = os.path.expanduser("~/Library/Application Support/LeadFlow")
BROWSER_DATA_DIR = os.path.join(DATA_DIR, "browser", "facebook")
COOKIES_FILE = os.path.join(DATA_DIR, "cookies", "facebook.json")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")

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

def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


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

    def __init__(self, proxy_server: str | None = None) -> None:
        self._proxy_server = proxy_server
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # -- Retry ---------------------------------------------------------------

    async def _retry(self, coro_fn, retries=3, backoff=(5, 15, 45)):
        """Retry an async callable up to *retries* times with exponential backoff."""
        last_error = None
        for i in range(retries):
            try:
                return await coro_fn()
            except Exception as e:
                last_error = e
                if i < retries - 1:
                    wait = backoff[i] if i < len(backoff) else backoff[-1]
                    logger.warning("Retry %d/%d after %ds: %s", i + 1, retries, wait, e)
                    await asyncio.sleep(wait)
        raise last_error

    # -- Lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        """Launch browser with anti-detection settings and persistent session."""
        os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

        self._playwright = await async_playwright().start()

        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if self._proxy_server:
            launch_args.append(f"--proxy-server={self._proxy_server}")

        # Use persistent context so login state survives across runs
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=False,
            args=launch_args,
            viewport=viewport,
            user_agent=user_agent,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            ignore_https_errors=True,
        )

        # Load saved cookies if available
        if os.path.exists(COOKIES_FILE):
            try:
                import json as _json
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
            "Facebook adapter initialized (viewport=%s, ua=%s...)",
            viewport,
            user_agent[:40],
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
            # Build search query
            query_parts = [keywords]
            if region:
                query_parts.append(region)
            if industry:
                query_parts.append(industry)
            query = " ".join(query_parts)

            # Navigate to Facebook search
            search_url = f"https://www.facebook.com/search/people/?q={query}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(3, 6)
            await _random_mouse_move(page)

            # Scroll to load more results
            await _human_scroll(page, times=4)
            await _random_delay(2, 4)

            # Extract search results
            # Facebook search result cards typically live in specific containers
            result_links = await page.query_selector_all(
                'div[role="article"] a[role="presentation"], '
                'div[data-pagelet*="SearchResult"] a[href*="/profile.php"], '
                'div[data-pagelet*="SearchResult"] a[href*="facebook.com/"]'
            )

            seen_urls: set[str] = set()

            for link in result_links[:30]:  # Cap at 30 to avoid over-scraping
                try:
                    href = await link.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue
                    # Only keep profile-like URLs
                    if "/profile.php" not in href and "facebook.com/" not in href:
                        continue
                    if "/search/" in href or "/hashtag/" in href:
                        continue

                    seen_urls.add(href)

                    # Try to extract name from the link or nearby elements
                    name = (await link.inner_text()).strip()
                    if not name:
                        name_el = await link.query_selector("span")
                        if name_el:
                            name = (await name_el.inner_text()).strip()

                    # Extract snippet (bio / mutual friends text) from parent
                    parent = await link.evaluate_handle("el => el.closest('div[role=\"article\"]') || el.parentElement.parentElement")
                    snippet = ""
                    try:
                        snippet_text = await parent.evaluate("el => el.innerText")
                        # Take text after the name as snippet
                        if name and name in snippet_text:
                            snippet = snippet_text.split(name, 1)[-1].strip()[:200]
                        else:
                            snippet = snippet_text[:200]
                    except Exception:
                        pass

                    # Extract platform_user_id from URL
                    platform_user_id = ""
                    if "profile.php?id=" in href:
                        platform_user_id = href.split("id=")[1].split("&")[0]
                    else:
                        # e.g. https://www.facebook.com/username
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
            # Navigate to the about page for richer data
            about_url = profile_url.rstrip("/") + "/about"
            await page.goto(about_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(3, 5)
            await _random_mouse_move(page)
            await _human_scroll(page, times=2)

            # Extract name
            name_el = await page.query_selector("h1")
            if name_el:
                profile_data["name"] = (await name_el.inner_text()).strip()

            # Extract intro / bio section
            intro_section = await page.query_selector(
                'div[data-pagelet="ProfileTileCollection"], '
                'div[data-pagelet="ProfileAppSection_0"]'
            )
            if intro_section:
                profile_data["bio"] = (await intro_section.inner_text()).strip()[:500]

            # Extract work and education from about page
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

            # Navigate to main profile to get recent posts
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
                    if len(text) > 20:  # Filter out short UI text
                        recent_posts.append(text[:300])
                        if len(recent_posts) >= 5:
                            break
                except Exception:
                    continue
            profile_data["recent_posts"] = recent_posts

            # Capture raw HTML for AI analysis
            profile_data["raw_html"] = await page.content()

            logger.info("get_profile: extracted profile for '%s'", profile_data.get("name", "unknown"))

        except Exception as e:
            logger.error("get_profile failed for %s: %s", profile_url, e)
            await _save_screenshot(page, "profile_error")

        return profile_data

    # -- Messaging -----------------------------------------------------------

    async def _send_message_impl(self, profile_url: str, message: str) -> bool:
        """Core implementation of send_message (called by the retry wrapper)."""
        if not self._page:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")

        page = self._page

        # Navigate to the profile
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        await _random_delay(3, 5)
        await _random_mouse_move(page)

        # Click the Message button
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

        # Wait for the message input to appear
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

        # Type message with human-like delays
        await msg_input.click()
        await _random_delay(0.5, 1.0)
        for char in message:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))

        await _random_delay(1, 2)

        # Send with Enter
        await page.keyboard.press("Enter")
        await _random_delay(2, 3)

        logger.info("send_message: message sent to %s (%d chars)", profile_url, len(message))
        return True

    async def send_message(self, profile_url: str, message: str) -> bool:
        """Send a direct message to a Facebook user (with automatic retry on failure)."""
        try:
            return await self._retry(lambda: self._send_message_impl(profile_url, message))
        except Exception as e:
            logger.error("send_message failed for %s after all retries: %s", profile_url, e)
            if self._page:
                await _save_screenshot(self._page, "send_error")
            return False

    # -- Inbox ---------------------------------------------------------------

    async def read_new_messages(self) -> list[dict]:
        """Read new/unread incoming messages from the Facebook Messenger inbox.

        Navigates to the Messenger page, looks for unread conversation
        indicators, opens each one (up to 10), reads the last inbound
        message, and returns structured data.

        Returns:
            list of dicts, each with:
                - sender_id   (str)  — extracted from the conversation URL
                - sender_name (str)
                - content     (str)  — text of the latest message
                - timestamp   (str)  — ISO-8601 UTC string (best-effort; may be empty)
        """
        if not self._page:
            raise RuntimeError("Adapter not initialized. Call initialize() first.")

        page = self._page
        results: list[dict] = []

        try:
            await page.goto(
                "https://www.facebook.com/messages/t/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await _random_delay(3, 5)
            await _random_mouse_move(page)

            # ------------------------------------------------------------------
            # Locate unread conversation entries in the left-hand sidebar.
            # Facebook marks unread threads with a bold label or a blue dot.
            # We try several selectors in order of specificity.
            # ------------------------------------------------------------------
            unread_selectors = [
                # Blue unread dot next to the thread row
                'div[role="navigation"] a[aria-label][href*="/messages/t/"]'
                ':has(span[data-testid="unread_count"])',
                # Bold thread name = unread in classic Messenger layout
                'div[role="navigation"] a[href*="/messages/t/"]'
                ':has(span[style*="font-weight: 700"])',
                # Fallback: all conversation links (we'll check content below)
                'div[role="navigation"] a[href*="/messages/t/"]',
                # Alternate navigation container
                'ul[role="listbox"] a[href*="/messages/t/"]',
                'div[data-pagelet="MWLeftRail"] a[href*="/messages/t/"]',
            ]

            thread_links: list = []
            for sel in unread_selectors:
                try:
                    found = await page.query_selector_all(sel)
                    if found:
                        thread_links = found
                        logger.info(
                            "read_new_messages: found %d thread links via selector '%s'",
                            len(found),
                            sel[:60],
                        )
                        break
                except Exception as sel_err:
                    logger.debug("Selector '%s' failed: %s", sel[:60], sel_err)

            if not thread_links:
                logger.info("read_new_messages: no unread conversation links found.")
                return []

            # Process up to 10 threads
            for link_el in thread_links[:10]:
                try:
                    await self._read_thread(page, link_el, results)
                except Exception as thread_err:
                    logger.warning("read_new_messages: error reading thread: %s", thread_err)

        except Exception as e:
            logger.error("read_new_messages failed: %s", e, exc_info=True)
            try:
                await _save_screenshot(page, "read_messages_error")
            except Exception:
                pass

        logger.info("read_new_messages: returning %d message(s).", len(results))
        return results

    async def _read_thread(
        self, page: "Page", link_el, results: list[dict]
    ) -> None:
        """Click a thread link, extract the last inbound message, append to results."""
        # Grab the href before clicking (clicking may navigate away)
        href: str = (await link_el.get_attribute("href")) or ""

        # Extract sender_id from the conversation URL.
        # URLs look like: /messages/t/123456789  or  /messages/t/username
        sender_id = ""
        if "/messages/t/" in href:
            sender_id = href.split("/messages/t/")[-1].split("?")[0].split("/")[0].strip()

        if not sender_id:
            logger.debug("_read_thread: could not extract sender_id from href=%s", href)
            return

        # Navigate to the conversation
        full_url = href if href.startswith("http") else f"https://www.facebook.com{href}"
        await page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
        await _random_delay(2, 4)

        # Try to get the thread participant name from the page heading
        sender_name = ""
        name_selectors = [
            'h2[dir="auto"]',
            'div[data-pagelet="MWThreadlist"] h2',
            'span[dir="auto"][style*="font-weight: 700"]',
            # Fallback: the <title> often contains the contact name
        ]
        for sel in name_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        sender_name = text
                        break
            except Exception:
                pass

        if not sender_name:
            # Last resort: pull from <title>
            try:
                title = await page.title()
                sender_name = title.split("|")[0].strip() if "|" in title else title.strip()
            except Exception:
                sender_name = sender_id  # use ID as fallback

        # ------------------------------------------------------------------
        # Extract the last message in the thread.
        # We look for message bubbles that are NOT from us (i.e. inbound).
        # ------------------------------------------------------------------
        message_content = ""
        timestamp_str = ""

        # Multiple fallback selectors for message bubbles
        bubble_selectors = [
            # Inbound messages often lack the "you" aria label
            'div[data-scope="messages_table"] div[dir="auto"]:not([aria-label*="You"])',
            'div[role="row"] div[dir="auto"]',
            'div[data-testid="message-container"] div[dir="auto"]',
            # Very generic fallback
            'div[class*="message"] div[dir="auto"]',
        ]

        for sel in bubble_selectors:
            try:
                bubbles = await page.query_selector_all(sel)
                if bubbles:
                    # Take the last bubble as the most recent message
                    last_bubble = bubbles[-1]
                    text = (await last_bubble.inner_text()).strip()
                    if text:
                        message_content = text
                        # Attempt to read a nearby timestamp
                        try:
                            ts_el = await last_bubble.query_selector(
                                'abbr[data-utime], span[data-utime], span[title*=":"]'
                            )
                            if ts_el:
                                timestamp_str = (
                                    await ts_el.get_attribute("data-utime")
                                    or await ts_el.get_attribute("title")
                                    or ""
                                )
                        except Exception:
                            pass
                        break
            except Exception as bsel_err:
                logger.debug("Bubble selector '%s' failed: %s", sel[:60], bsel_err)

        if not message_content:
            logger.debug("_read_thread: no message content found for sender_id=%s", sender_id)
            return

        results.append(
            {
                "sender_id": sender_id,
                "sender_name": sender_name,
                "content": message_content,
                "timestamp": timestamp_str,
            }
        )

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
