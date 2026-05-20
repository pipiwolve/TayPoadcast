"""Academic domain fetcher: arXiv recent papers."""

import asyncio
import re

import httpx

from fetcher.base import BaseFetcher, DailyDigest, NewsItem

ARXIV_API = "https://export.arxiv.org/api/query"


class AcademicFetcher(BaseFetcher):
    domain = "academic"

    async def fetch(self) -> DailyDigest:
        all_items = []
        categories = [
            ("cs.AI", "AI"),
            ("cs.CL", "NLP"),
            ("cs.CV", "CV"),
            ("cs.LG", "ML"),
        ]

        async with httpx.AsyncClient() as client:
            tasks = [self._fetch_category(client, cat, label) for cat, label in categories]
            results = await asyncio.gather(*tasks)
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

    async def _fetch_category(
        self, client: httpx.AsyncClient, category: str, label: str
    ) -> list[NewsItem]:
        try:
            resp = await client.get(
                ARXIV_API,
                params={
                    "search_query": f"cat:{category}",
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": 10,
                },
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"  [arXiv:{label}] 请求失败: {e}")
            return []

        text = resp.text
        entries = text.split("<entry>")[1:]

        items = []
        for entry in entries[:5]:
            title_match = _xml_text(entry, "title")
            summary_match = _xml_text(entry, "summary")
            link = ""
            link_match = re.search(r'<id>(https?://arxiv\.org/abs/[^<]+)</id>', entry)
            if link_match:
                link = link_match.group(1)

            if title_match:
                items.append(NewsItem(
                    title=title_match.strip()[:150],
                    url=link,
                    description=summary_match.strip()[:200] if summary_match else "",
                    source=f"arXiv ({label})",
                    stars=0,
                ))
        return items


def _xml_text(xml: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    if match:
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return ""
