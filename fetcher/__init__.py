"""Fetcher package — pluggable domain modules."""

import httpx

from fetcher.base import BaseFetcher, DailyDigest, NewsItem
from fetcher.tech import TechFetcher

__all__ = [
    "BaseFetcher", "DailyDigest", "NewsItem", "TechFetcher",
    "fetch_all", "fetch_github_trending", "fetch_hn_top_stories", "fetch_hn_ai_articles",
]

# ---------------------------------------------------------------------------
# Backward-compatible re-exports (old code does "from fetcher import fetch_all")
# ---------------------------------------------------------------------------


async def fetch_all() -> DailyDigest:
    f = TechFetcher()
    return await f.fetch()


async def fetch_github_trending(client: httpx.AsyncClient) -> list[NewsItem]:
    f = TechFetcher()
    return await f._fetch_github_trending(client)


async def fetch_hn_top_stories(client: httpx.AsyncClient, limit: int = 15) -> list[NewsItem]:
    f = TechFetcher()
    return await f._fetch_hn_top_stories(client, limit)


async def fetch_hn_ai_articles(client: httpx.AsyncClient, limit: int = 8) -> list[NewsItem]:
    f = TechFetcher()
    return await f._fetch_hn_ai_articles(client, limit)
