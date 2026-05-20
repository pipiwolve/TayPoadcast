"""Backward-compatible re-export. New code should use fetcher/ package directly."""
from fetcher.base import DailyDigest, NewsItem
from fetcher.tech import TechFetcher


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
