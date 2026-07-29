"""One shared headless browser for every browser-driven source.

Launching Chromium per search costs a couple of seconds and ~350MB of RAM. With one user that is
merely slow; with ten pressing 🔍 at the same time it is the whole server. So the process keeps a
single browser alive and hands out throwaway contexts, and a semaphore caps how many pages exist
at once. The queue is the point: a spike becomes a wait instead of an OOM kill.

Contexts are never reused — each search gets a clean cookie jar, so one user's session can't leak
into another's prices.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from .config import settings

log = logging.getLogger("ticketcatch")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1500, "height": 1100}
LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",  # /dev/shm is tiny in containers; without this Chromium crashes
    "--disable-gpu",
    "--blink-settings=imagesEnabled=false",  # we read text and data attributes, never pixels
]

_playwright = None
_browser = None
_launch_lock = asyncio.Lock()
_slots: asyncio.Semaphore | None = None


class BrowserUnavailable(RuntimeError):
    """Playwright isn't installed or Chromium won't start — the source should degrade, not crash."""


def _semaphore() -> asyncio.Semaphore:
    """Created lazily: a Semaphore binds to the running loop, and settings load before there is one."""
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(max(1, settings.browser_concurrency))
    return _slots


async def _get_browser():
    """The live browser, relaunched if it died. Serialized so a burst launches one, not five."""
    global _playwright, _browser
    async with _launch_lock:
        if _browser is not None and _browser.is_connected():
            return _browser
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise BrowserUnavailable(f"playwright not installed ({e})") from e
        try:
            if _playwright is None:
                _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(headless=True, args=LAUNCH_ARGS)
        except Exception as e:
            raise BrowserUnavailable(f"chromium failed to start ({e})") from e
        log.info("browser launched (concurrency %s)", settings.browser_concurrency)
        return _browser


@asynccontextmanager
async def new_page(locale: str = "en-US") -> AsyncIterator:
    """A fresh page in its own context. Blocks while all browser slots are busy."""
    async with _semaphore():
        browser = await _get_browser()
        context = await browser.new_context(user_agent=UA, locale=locale, viewport=VIEWPORT)
        try:
            yield await context.new_page()
        finally:
            try:
                await context.close()
            except Exception as e:  # a dead browser must not mask the caller's own error
                log.warning("context close failed: %s", e)


async def shutdown() -> None:
    """Release Chromium on a clean exit so pm2 restarts don't leak processes."""
    global _playwright, _browser
    if _browser is not None:
        try:
            await _browser.close()
        except Exception as e:
            log.warning("browser close failed: %s", e)
        _browser = None
    if _playwright is not None:
        try:
            await _playwright.stop()
        except Exception as e:
            log.warning("playwright stop failed: %s", e)
        _playwright = None
