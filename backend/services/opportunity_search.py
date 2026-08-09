"""Web search for real opportunity sources (Serper API or DuckDuckGo fallback)."""

import os
from urllib.parse import urlparse

import requests


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
            return []
        data = resp.json()
    except requests.RequestException:
        return []

    results = []
    for item in data.get("organic", [])[:max_results]:
        row = _normalize_result(item.get("title"), item.get("snippet"), item.get("link"))
        if row:
            results.append(row)
    return results


def _search_duckduckgo(query, max_results=8):
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
    except Exception:
        return []
    return results


def search_web(query, max_results=8):
    """Search the web; prefer Serper when configured."""
    results = _search_serper(query, max_results=max_results)
    if results:
        return results
    return _search_duckduckgo(query, max_results=max_results)


def collect_venture_search_results(venture, max_per_query=6):
    """Run venture-specific queries and dedupe by URL."""
    seen = set()
    collected = []
    for query in venture.get("search_queries", [])[:6]:
        for row in search_web(query, max_results=max_per_query):
            url_key = row["url"].lower().rstrip("/")
            if url_key in seen:
                continue
            seen.add(url_key)
            row["search_query"] = query
            collected.append(row)
    return collected
