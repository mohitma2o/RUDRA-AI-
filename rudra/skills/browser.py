"""Browser automation skill helpers."""

import urllib.parse
import webbrowser
import sys
import subprocess


def open_url(url: str) -> str:
    """Open the provided URL in the default browser."""
    if not url:
        return "No URL provided."

    try:
        webbrowser.open(url)
        return f"Opened URL: {url}"
    except Exception as exc:
        return f"Failed to open URL: {exc}"


def google_search(query: str) -> str:
    """Perform a Google search for the given query."""
    if not query:
        return "No search query provided."

    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    return open_url(url)


def compose_email(to: str, subject: str, body: str) -> str:
    """Open the default mail client with a mailto: draft."""
    if not to:
        return "No recipient address provided."

    params = {
        "subject": subject or "",
        "body": body or "",
    }
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    mailto = f"mailto:{urllib.parse.quote(to)}?{query}"
    return open_url(mailto)
