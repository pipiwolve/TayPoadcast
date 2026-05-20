"""General news fetcher: RSS feeds from multiple outlets."""

import asyncio
import re

import httpx

from fetcher.base import BaseFetcher, DailyDigest, NewsItem

# Public RSS feeds accessible from GitHub Actions
RSS_FEEDS = [
    ("https://rsshub.app/weibo/search/hot", "微博热搜"),
    ("https://rsshub.app/zhihu/hotlist", "知乎热榜"),
    ("http://rss.sina.com.cn/news/marquee/ddt.xml", "新浪要闻"),
]


class GeneralFetcher(BaseFetcher):
    domain = "general"

    async def fetch(self) -> DailyDigest:
        async with httpx.AsyncClient() as client:
            tasks = [self._fetch_rss(client, url, label) for url, label in RSS_FEEDS]
            results = await asyncio.gather(*tasks)

        all_items = []
        for r in results:
            all_items.extend(r)

        seen = set()
        unique = []
        for item in all_items:
            key = item.title.lower()[:80]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        unique.sort(key=lambda x: x.stars, reverse=True)
        return DailyDigest(domain=self.domain, items=unique[:20])

    async def _fetch_rss(
        self, client: httpx.AsyncClient, url: str, label: str
    ) -> list[NewsItem]:
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/rss+xml, application/xml, text/xml",
                },
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"  [{label}] 请求失败: {e}")
            return []

        text = resp.text
        # Try RSS <item> first, then Atom <entry>
        items_xml = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
        if not items_xml:
            items_xml = re.findall(r"<entry>(.*?)</entry>", text, re.DOTALL)

        items = []
        for entry in items_xml[:10]:
            title = _rss_text(entry, "title")
            link = _rss_text(entry, "link")
            desc = _rss_text(entry, "description")

            if title:
                items.append(NewsItem(
                    title=title.strip()[:150],
                    url=link or url,
                    description=desc.strip()[:200] if desc else "",
                    source=label,
                    stars=0,
                ))
        return items


def _rss_text(xml: str, tag: str) -> str:
    # Try standard closing tag
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    if match:
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    # Try self-closing tag with href attribute (Atom-style links)
    if tag == "link":
        match = re.search(rf'<{tag}[^>]*href="([^"]+)"', xml)
        if match:
            return match.group(1)
    return ""
