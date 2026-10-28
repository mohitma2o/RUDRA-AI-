"""Browser automation tools: YouTube playback, web search, web navigation.

Uses Playwright with a persistent context located at .rudra/browser/ to preserve
cookies, media playback states, and sessions across assistant turns.
"""

import asyncio
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Optional

from .registry import Tier, tool

# Persistent profile directory in repo root: .rudra/browser/
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BROWSER_PROFILE_DIR = _REPO_ROOT / ".rudra" / "browser"


def _ensure_profile_dir() -> Path:
    _BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return _BROWSER_PROFILE_DIR


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
    def _play() -> str:
        if not query.strip():
            return "Please specify what you would like to play on YouTube."

        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"

        try:
            from playwright.sync_api import sync_playwright
            profile_dir = _ensure_profile_dir()

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    args=["--autoplay-policy=no-user-gesture-required"],
                )
                page = context.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=12000)

                # Wait for video link
                video_selector = "ytd-video-renderer a#video-title"
                try:
                    page.wait_for_selector(video_selector, timeout=6000)
                    first_video = page.query_selector(video_selector)
                    if first_video:
                        video_title = first_video.inner_text().strip()
                        video_href = first_video.get_attribute("href")
                        if video_href:
                            full_url = f"https://www.youtube.com{video_href}"
                            page.goto(full_url, wait_until="domcontentloaded", timeout=10000)
                            return f"Playing '{video_title}' on YouTube."
                except Exception:
                    # If selector wait times out, stay on search results page
                    pass
                return f"Opened YouTube search for '{query}'."
        except Exception:
            # Fall back to default browser
            import webbrowser
            webbrowser.open(search_url)
            return f"Opened YouTube search for '{query}' in your browser."

    return await asyncio.to_thread(_play)


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
