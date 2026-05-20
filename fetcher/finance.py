"""Finance domain fetcher: CLS telegraph + WallstreetCN live."""

import asyncio

import httpx

from fetcher.base import BaseFetcher, DailyDigest, NewsItem

CLS_TELEGRAPH_URL = "https://www.cls.cn/nodeapi/telegraphList"
WALLSTREETCN_URL = "https://api-one.wallstcn.com/apiv1/content/lives"


class FinanceFetcher(BaseFetcher):
    domain = "finance"

    async def fetch(self) -> DailyDigest:
        async with httpx.AsyncClient() as client:
            cls_task = self._fetch_cls_telegraph(client)
            wall_task = self._fetch_wallstreetcn(client)
            results = await asyncio.gather(cls_task, wall_task)

        all_items = results[0] + results[1]
        seen = set()
        unique = []
        for item in all_items:
            key = item.title[:60]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        unique.sort(key=lambda x: x.stars, reverse=True)
        return DailyDigest(domain=self.domain, items=unique[:25])

    async def _fetch_cls_telegraph(self, client: httpx.AsyncClient) -> list[NewsItem]:
        try:
            resp = await client.get(
                CLS_TELEGRAPH_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://www.cls.cn/telegraph",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            rolls = data.get("data", {}).get("roll_data", [])
        except Exception as e:
            print(f"  [财联社] 请求失败: {e}")
            return []

        items = []
        for roll in rolls[:15]:
            title = (roll.get("title") or roll.get("content") or "").strip()
            if not title:
                continue
            items.append(NewsItem(
                title=title[:150],
                url=f"https://www.cls.cn/detail/{roll.get('id', '')}",
                description=(roll.get("content") or roll.get("brief", ""))[:200],
                source="财联社电报",
                stars=roll.get("sharenum", 0) or 0,
            ))
        return items

    async def _fetch_wallstreetcn(self, client: httpx.AsyncClient) -> list[NewsItem]:
        try:
            resp = await client.get(
                WALLSTREETCN_URL,
                params={
                    "channel": "global-channel",
                    "limit": 20,
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://wallstreetcn.com/",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            lives = data.get("data", {}).get("items", [])
        except Exception as e:
            print(f"  [华尔街见闻] 请求失败: {e}")
            return []

        items = []
        for live in lives[:15]:
            title = (live.get("title") or live.get("content_text") or "").strip()
            if not title:
                continue
            items.append(NewsItem(
                title=title[:150],
                url=f"https://wallstreetcn.com/livenews/{live.get('id', '')}",
                description=(live.get("content_text") or "")[:200],
                source="华尔街见闻",
                stars=0,
            ))
        return items
