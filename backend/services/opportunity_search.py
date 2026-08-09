"""Web search for real opportunity sources (Serper API, ddgs, or DuckDuckGo fallback)."""

import logging
import os
import re
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def _normalize_url(url):
    u = (url or "").strip()
    if not u:
        return ""
    u = u.rstrip("/").lower()
    if u.startswith("http://"):
        u = "https://" + u[7:]
    return u


def _normalize_result(title, body, href, source_name=None):
    href = (href or "").strip()
    if not href or not title:
        return None
    parsed = urlparse(href)
    if not parsed.scheme or not parsed.netloc:
        return None
    domain = parsed.netloc.replace("www.", "")
    return {
        "title": (title or "").strip()[:500],
        "snippet": (body or "").strip()[:1500],
        "url": href[:1000],
        "source_name": (source_name or domain)[:255],
    }


def _search_serper(query, max_results=8):
    api_key = (os.environ.get("SERPER_API_KEY") or "").strip()
    if not api_key:
        return []

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=25,
        )
        if resp.status_code != 200:
            logger.warning("Serper search failed: status %s", resp.status_code)
            return []
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("Serper search error: %s", exc)
        return []

    results = []
    for item in data.get("organic", [])[:max_results]:
        row = _normalize_result(item.get("title"), item.get("snippet"), item.get("link"))
        if row:
            results.append(row)
    return results


def _search_ddgs(query, max_results=8):
    """Primary free search — ddgs package (successor to duckduckgo_search)."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []

    results = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                row = _normalize_result(
                    item.get("title"),
                    item.get("body") or item.get("snippet"),
                    item.get("href") or item.get("url"),
                )
                if row:
                    results.append(row)
    except Exception as exc:
        logger.warning("ddgs search error for %r: %s", query[:60], exc)
    return results


def _search_duckduckgo_legacy(query, max_results=8):
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    results = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                row = _normalize_result(item.get("title"), item.get("body"), item.get("href"))
                if row:
                    results.append(row)
    except Exception as exc:
        logger.warning("duckduckgo_search error: %s", exc)
    return results


def _search_duckduckgo_html(query, max_results=8):
    """Last-resort HTML scrape when API packages fail."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; CEOOpportunityBot/1.0)"},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        html = resp.text
    except requests.RequestException:
        return []

    results = []
    blocks = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>.*?class="result__snippet"[^>]*>([^<]*)',
        html,
        re.DOTALL,
    )
    for href, title, snippet in blocks[:max_results]:
        if href.startswith("//"):
            href = "https:" + href
        row = _normalize_result(title, snippet, href)
        if row:
            results.append(row)
    return results


def search_web(query, max_results=8):
    """Search the web; try Serper, then ddgs, then legacy DDG, then HTML."""
    for fn in (_search_serper, _search_ddgs, _search_duckduckgo_legacy, _search_duckduckgo_html):
        results = fn(query, max_results=max_results)
        if results:
            return results
    return []


def build_url_allowlist(search_results):
    """URLs and domains the AI may cite (same-domain apply pages allowed)."""
    allowed_urls = set()
    allowed_domains = set()
    for row in search_results:
        raw = row.get("url") or ""
        norm = _normalize_url(raw)
        if norm:
            allowed_urls.add(norm)
        parsed = urlparse(raw)
        if parsed.netloc:
            allowed_domains.add(parsed.netloc.lower().replace("www.", ""))
    return allowed_urls, allowed_domains


def url_is_verified(url, allowed_urls, allowed_domains):
    norm = _normalize_url(url)
    if not norm:
        return False
    if norm in allowed_urls:
        return True
    parsed = urlparse(norm)
    domain = parsed.netloc.replace("www.", "")
    return domain in allowed_domains


def collect_venture_search_results(venture, max_per_query=6):
    """Run venture-specific queries and dedupe by URL."""
    seen = set()
    collected = []
    for query in venture.get("search_queries", [])[:6]:
        for row in search_web(query, max_results=max_per_query):
            url_key = _normalize_url(row["url"])
            if not url_key or url_key in seen:
                continue
            seen.add(url_key)
            row["search_query"] = query
            collected.append(row)
    return collected
