"""Fetch AI news from GitHub Trending and Hacker News."""

import asyncio
import re
from dataclasses import dataclass, field

import httpx

GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"


@dataclass
class NewsItem:
    title: str
    url: str
    description: str
    source: str  # "github" or "hackernews"
    stars: int = 0
    language: str = ""

    def summary(self) -> str:
        return f"[{self.source}] {self.title} — {self.description}"


@dataclass
class DailyDigest:
    items: list[NewsItem] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        lines = []
        for i, item in enumerate(self.items, 1):
            lines.append(f"{i}. [{item.source.upper()}] {item.title}")
            if item.description:
                lines.append(f"   简介: {item.description}")
            if item.stars:
                lines.append(f"   ⭐ {item.stars}")
            if item.language:
                lines.append(f"   语言: {item.language}")
        return "\n".join(lines)


async def fetch_github_trending(client: httpx.AsyncClient) -> list[NewsItem]:
    """Scrape GitHub Trending page for daily trending repos."""
    headers = {
        "User-Agent": "AI-News-Podcast/1.0",
        "Accept": "text/html",
    }
    try:
        resp = await client.get(GITHUB_TRENDING_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [GitHub] 请求失败: {e}")
        return []

    html = resp.text
    items = []

    repo_blocks = re.findall(
        r'<article[^>]*class="Box-row"[^>]*>(.*?)</article>', html, re.DOTALL
    )

    for block in repo_blocks[:10]:
        # Extract href path: /owner/repo → owner/repo
        href_match = re.search(r'h2[^>]*>\s*<a[^>]*href="([^"]+)"', block)
        desc_match = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
        lang_match = re.search(r'<span[^>]*itemprop="programmingLanguage"[^>]*>([^<]+)', block)
        stars_match = re.search(r'(\d[\d,]*)\s*stars\s+today', block, re.IGNORECASE)

        if href_match:
            path = href_match.group(1).strip()
            name = path.strip("/")  # /owner/repo → owner/repo
            desc = ""
            if desc_match:
                desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
            stars = 0
            if stars_match:
                try:
                    stars = int(stars_match.group(1).replace(",", ""))
                except ValueError:
                    pass

            items.append(NewsItem(
                title=f"{name}",
                url=f"https://github.com{path}",
                description=desc[:200] if desc else "",
                source="GitHub热门",
                stars=stars,
                language=lang_match.group(1).strip() if lang_match else "",
            ))

    return items


async def fetch_hn_top_stories(client: httpx.AsyncClient, limit: int = 10) -> list[NewsItem]:
    """Fetch top Hacker News stories, filtered for AI/tech relevance."""
    try:
        resp = await client.get(HN_TOP_URL, timeout=15)
        resp.raise_for_status()
        story_ids = resp.json()[:30]
    except Exception as e:
        print(f"  [HN] 获取列表失败: {e}")
        return []

    ai_keywords = [
        "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
        "model", "transformer", "diffusion", "neural", "ml", "deep learning",
        "agent", "agi", "token", "embedding", "vector", "rag",
        "langchain", "cuda", "gpu", "nvidia", "pytorch", "tensorflow",
        "hugging face", "opensource", "open source", "github", "copilot",
        "cursor", "vibe cod", "notebooklm", "tts", "speech",
    ]

    items = []
    for sid in story_ids[:20]:
        try:
            r = await client.get(HN_ITEM_URL.format(sid), timeout=10)
            r.raise_for_status()
            story = r.json()
        except Exception:
            continue

        if not story or story.get("type") != "story":
            continue

        title = (story.get("title") or "").lower()
        desc = ""
        if story.get("text"):
            desc = story["text"][:200]

        is_ai_related = any(kw in title for kw in ai_keywords)
        is_high_score = story.get("score", 0) >= 100

        if is_ai_related or (is_high_score and story.get("score", 0) >= 300):
            url = story.get("url") or f"https://news.ycombinator.com/item?id={sid}"
            items.append(NewsItem(
                title=story.get("title", "Untitled"),
                url=url,
                description=desc[:200],
                source="HackerNews",
                stars=story.get("score", 0),
            ))

        if len(items) >= limit:
            break

    return items


async def fetch_hn_ai_articles(client: httpx.AsyncClient, limit: int = 5) -> list[NewsItem]:
    """Search HN Algolia for recent popular AI articles."""
    try:
        url = f"{HN_ALGOLIA_SEARCH}?query=AI+OR+LLM+OR+GPT+OR+model&tags=story&numericFilters=points>50&hitsPerPage={limit}"
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except Exception as e:
        print(f"  [HN搜索] 请求失败: {e}")
        return []

    items = []
    for hit in hits[:limit]:
        items.append(NewsItem(
            title=hit.get("title", "Untitled"),
            url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            description="",
            source="HackerNews",
            stars=hit.get("points", 0),
        ))

    return items


async def fetch_all() -> DailyDigest:
    """Fetch and merge news from all sources."""
    async with httpx.AsyncClient() as client:
        github_task = fetch_github_trending(client)
        hn_top_task = fetch_hn_top_stories(client)
        hn_ai_task = fetch_hn_ai_articles(client)

        github_items, hn_top, hn_ai = await asyncio.gather(
            github_task, hn_top_task, hn_ai_task
        )

    all_items = github_items + hn_top + hn_ai
    seen = set()
    unique = []
    for item in all_items:
        key = item.title.lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    unique.sort(key=lambda x: x.stars, reverse=True)
    return DailyDigest(items=unique[:12])


if __name__ == "__main__":
    digest = asyncio.run(fetch_all())
    print(f"获取到 {len(digest.items)} 条新闻:\n")
    print(digest.to_prompt_context())
