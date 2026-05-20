"""Fetcher package — pluggable domain modules."""

from fetcher.base import BaseFetcher, DailyDigest, NewsItem
from fetcher.tech import TechFetcher

__all__ = ["BaseFetcher", "DailyDigest", "NewsItem", "TechFetcher"]

# ---------------------------------------------------------------------------
# Backward-compatible re-exports (old code does "from fetcher import fetch_all")
# ---------------------------------------------------------------------------


async def fetch_all():
    f = TechFetcher()
    return await f.fetch()


# Direct function compatibility for old callers
async def fetch_github_trending(client):
    f = TechFetcher()
    return await f._fetch_github_trending(client)


async def fetch_hn_top_stories(client, limit=15):
    f = TechFetcher()
    return await f._fetch_hn_top_stories(client, limit)


async def fetch_hn_ai_articles(client, limit=8):
    f = TechFetcher()
    return await f._fetch_hn_ai_articles(client, limit)
