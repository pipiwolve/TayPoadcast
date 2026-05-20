"""Fetcher package — pluggable domain modules."""

import httpx

from fetcher.academic import AcademicFetcher
from fetcher.base import BaseFetcher, DailyDigest, NewsItem
from fetcher.finance import FinanceFetcher
from fetcher.general import GeneralFetcher
from fetcher.tech import TechFetcher

__all__ = [
    "AcademicFetcher", "BaseFetcher", "DailyDigest", "NewsItem",
    "FinanceFetcher", "GeneralFetcher", "TechFetcher",
    "FETCHER_REGISTRY",
    "fetch_all", "fetch_github_trending", "fetch_hn_top_stories", "fetch_hn_ai_articles",
]

# Registry: domain -> fetcher class
FETCHER_REGISTRY = {
    "tech": TechFetcher,
    "finance": FinanceFetcher,
    "academic": AcademicFetcher,
    "general": GeneralFetcher,
}

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
