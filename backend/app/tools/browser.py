"""Browser automation tools: YouTube playback, web search, web navigation.

Uses Playwright with a persistent context in the user data directory to preserve
cookies, media playback states, and sessions across assistant turns.
"""

import asyncio
import queue
import threading
import urllib.parse
from concurrent.futures import Future
from pathlib import Path
from typing import Callable, Optional, Protocol

from ..paths import data_dir
from .registry import Tier, tool


class _VideoLink(Protocol):
    def inner_text(self) -> str: ...

    def get_attribute(self, name: str) -> Optional[str]: ...


class _BrowserPage(Protocol):
    def is_closed(self) -> bool: ...

    def goto(self, url: str, *, wait_until: str, timeout: int) -> object: ...

    def wait_for_selector(self, selector: str, *, timeout: int) -> object: ...

    def query_selector(self, selector: str) -> Optional[_VideoLink]: ...


class _BrowserContext(Protocol):
    pages: list[_BrowserPage]

    def new_page(self) -> _BrowserPage: ...

    def close(self) -> None: ...


class _Chromium(Protocol):
    def launch_persistent_context(
        self, *, user_data_dir: str, headless: bool, args: list[str]
    ) -> _BrowserContext: ...


class _Playwright(Protocol):
    chromium: _Chromium

    def stop(self) -> None: ...


class _BrowserRuntime:
    """Own Playwright and its persistent context on one dedicated thread."""

    def __init__(self, playwright_factory: Optional[Callable[[], _Playwright]] = None):
        self._playwright_factory = playwright_factory or self._start_playwright
        self._requests: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._closed = False

    @staticmethod
    def _start_playwright() -> _Playwright:
        from playwright.sync_api import sync_playwright

        return sync_playwright().start()

    def submit(self, operation: Callable[[_BrowserPage], str]) -> Future[str]:
        future: Future[str] = Future()
        with self._lock:
            if self._closed:
                raise RuntimeError("The browser runtime has been closed.")
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._serve,
                    name="rudra-playwright",
                    daemon=True,
                )
                self._thread.start()
            self._requests.put((operation, future))
        return future

    def _serve(self) -> None:
        playwright = None
        context: Optional[_BrowserContext] = None
        page: Optional[_BrowserPage] = None
        startup_error: Optional[Exception] = None
        try:
            playwright = self._playwright_factory()
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(_ensure_profile_dir()),
                headless=False,
                args=["--autoplay-policy=no-user-gesture-required"],
            )
            page = context.pages[0] if context.pages else context.new_page()
        except Exception as exc:
            startup_error = exc

        try:
            while True:
                request = self._requests.get()
                if request is None:
                    break
                operation, future = request
                if not future.set_running_or_notify_cancel():
                    continue
                if startup_error:
                    future.set_exception(startup_error)
                    continue
                assert context is not None and page is not None
                try:
                    if page.is_closed():
                        page = context.new_page()
                    future.set_result(operation(page))
                except Exception as exc:
                    future.set_exception(exc)
        finally:
            try:
                if context is not None:
                    context.close()
            finally:
                if playwright is not None:
                    playwright.stop()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            thread = self._thread
            if thread is not None:
                self._requests.put(None)
            else:
                self._closed = False
                return
        if thread is not None:
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("The browser runtime did not stop within 10 seconds.")
            with self._lock:
                if self._thread is thread:
                    self._thread = None
                    self._requests = queue.Queue()
                    self._closed = False


_browser_runtime = _BrowserRuntime()


def close_browser_runtime() -> None:
    """Close the persistent browser context during backend shutdown."""
    _browser_runtime.close()


def _ensure_profile_dir() -> Path:
    profile_dir = data_dir() / "browser"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


@tool(
    name="play_youtube",
    description="Search and play a video or music on YouTube in the browser.",
    tier=Tier.AUTO,
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The song, video, or topic to play"}
        },
        "required": ["query"],
    },
)
async def play_youtube(query: str) -> str:
    """Search YouTube and play the top result using Playwright or system browser."""
    if not query.strip():
        return "Please specify what you would like to play on YouTube."

    encoded = urllib.parse.quote_plus(query)
    search_url = f"https://www.youtube.com/results?search_query={encoded}"

    def _play(page: _BrowserPage) -> str:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        page.goto(search_url, wait_until="domcontentloaded", timeout=12000)
        video_selector = "ytd-video-renderer a#video-title"
        try:
            page.wait_for_selector(video_selector, timeout=6000)
        except PlaywrightTimeoutError:
            return f"Opened YouTube search for '{query}'."

        first_video = page.query_selector(video_selector)
        if first_video:
            video_title = first_video.inner_text().strip()
            video_href = first_video.get_attribute("href")
            if video_href:
                page.goto(
                    f"https://www.youtube.com{video_href}",
                    wait_until="domcontentloaded",
                    timeout=10000,
                )
                return f"Playing '{video_title}' on YouTube."
        return f"Opened YouTube search for '{query}'."

    try:
        return await asyncio.wrap_future(_browser_runtime.submit(_play))
    except Exception as exc:
        import webbrowser

        webbrowser.open(search_url)
        return f"Playwright failed ({exc}); opened YouTube search for '{query}' in your browser."


@tool(
    name="open_url",
    description="Open a web page URL in the browser.",
    tier=Tier.AUTO,
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The complete URL to open"}
        },
        "required": ["url"],
    },
)
async def open_url(url: str) -> str:
    def _open() -> str:
        if not url.strip():
            return "No URL specified."
        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url
        import webbrowser
        webbrowser.open(clean_url)
        return f"Opened {clean_url} in your browser."
    return await asyncio.to_thread(_open)


@tool(
    name="google_search",
    description="Perform a web search on Google.",
    tier=Tier.AUTO,
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query terms"}
        },
        "required": ["query"],
    },
)
async def google_search(query: str) -> str:
    def _search() -> str:
        if not query.strip():
            return "No search query specified."
        encoded = urllib.parse.quote_plus(query.strip())
        target_url = f"https://www.google.com/search?q={encoded}"
        import webbrowser
        webbrowser.open(target_url)
        return f"Searching Google for '{query}'."
    return await asyncio.to_thread(_search)
