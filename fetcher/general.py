"""General news fetcher: Bilibili hot search + Sina news roll API."""

import asyncio

import httpx

from fetcher.base import BaseFetcher, DailyDigest, NewsItem

BILIBILI_API = "https://api.bilibili.com/x/web-interface/wbi/search/square"
SINA_ROLL_API = "https://feed.mix.sina.com.cn/api/roll/get"


class GeneralFetcher(BaseFetcher):
    domain = "general"

    async def fetch(self) -> DailyDigest:
        async with httpx.AsyncClient() as client:
            bili_task = self._fetch_bilibili(client)
            sina_task = self._fetch_sina_roll(client)
            results = await asyncio.gather(bili_task, sina_task)

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
        return DailyDigest(domain=self.domain, items=unique[:25])

    async def _fetch_bilibili(self, client: httpx.AsyncClient) -> list[NewsItem]:
        try:
            resp = await client.get(
                BILIBILI_API,
                params={"limit": 50},
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com/",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            items_data = data.get("data", {}).get("trending", {}).get("list", [])
        except Exception as e:
            print(f"  [B站热搜] 请求失败: {e}")
            return []

        items = []
        for it in items_data[:20]:
            keyword = it.get("keyword", "").strip()
            if not keyword:
                continue
            show_name = it.get("show_name", "") or ""
            items.append(NewsItem(
                title=f"{keyword}  {show_name}".strip()[:150],
                url=f"https://search.bilibili.com/all?keyword={keyword}",
                description=f"B站热搜: {keyword}",
                source="B站热搜",
                stars=it.get("heat", 0) or 0,
            ))
        return items

    async def _fetch_sina_roll(self, client: httpx.AsyncClient) -> list[NewsItem]:
        try:
            resp = await client.get(
                SINA_ROLL_API,
                params={
                    "pageid": "153",
                    "lid": "2509",
                    "k": "",
                    "num": 20,
                    "page": 1,
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://news.sina.com.cn/",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            items_data = data.get("result", {}).get("data", [])
        except Exception as e:
            print(f"  [新浪新闻] 请求失败: {e}")
            return []

        items = []
        for it in items_data[:15]:
            title = (it.get("title") or it.get("intro") or "").strip()
            if not title:
                continue
            url = it.get("url", "")
            ctime = it.get("ctime", "")
            items.append(NewsItem(
                title=title[:150],
                url=url,
                description=(it.get("intro") or "")[:200],
                source=f"新浪新闻 · {ctime}",
                stars=int(it.get("total_num", 0) or 0),
            ))
        return items
