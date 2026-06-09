"""Fetch a job description from a URL.

Best-effort and non-fatal: returns extracted text, or "" if the page can't be
reached or scraped (many boards block bots). The UI always falls back to manual
paste, so this never raises into the request path.

If FIRECRAWL_API_KEY is set, Firecrawl is used first (handles JS-heavy/blocked
boards like LinkedIn/Indeed); otherwise a plain httpx GET + BeautifulSoup main
-text extraction is used.
"""
import logging
import os
import re

logger = logging.getLogger("resume.jd")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text or "")
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def _firecrawl(url: str) -> str:
    key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
    if not key:
        return ""
    try:
        import httpx

        r = httpx.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {key}"},
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
        return _clean((data.get("data") or {}).get("markdown") or "")
    except Exception:
        logger.warning("[jd] firecrawl scrape failed for %s", url, exc_info=True)
        return ""


def _httpx_bs4(url: str) -> str:
    try:
        import httpx
        from bs4 import BeautifulSoup

        r = httpx.get(url, headers=_HEADERS, timeout=30, follow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()
        # Prefer the main/article region when present; fall back to the body.
        main = soup.find("main") or soup.find("article") or soup.body or soup
        return _clean(main.get_text("\n"))
    except Exception:
        logger.warning("[jd] httpx/bs4 scrape failed for %s", url, exc_info=True)
        return ""


def fetch_jd(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return _firecrawl(url) or _httpx_bs4(url)
