"""Finance domain fetcher: Xueqiu hot posts + CLS news flash."""

import asyncio
import re

import httpx

from fetcher.base import BaseFetcher, DailyDigest, NewsItem

XUEQIU_HOT_URL = "https://xueqiu.com/statuses/hot/listV2.json"
XUEQIU_REFERER = "https://xueqiu.com"
CLS_TELEGRAPH_URL = "https://www.cls.cn/api/telegraph/list"


class FinanceFetcher(BaseFetcher):
    domain = "finance"

    async def fetch(self) -> DailyDigest:
        async with httpx.AsyncClient() as client:
            # Need cookies for xueqiu; get them first
            try:
                await client.get("https://xueqiu.com", headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }, timeout=15)
            except Exception:
                pass

            xueqiu_task = self._fetch_xueqiu_hot(client)
            cls_task = self._fetch_cls_telegraph(client)

            xueqiu_items, cls_items = await asyncio.gather(xueqiu_task, cls_task)

        all_items = xueqiu_items + cls_items
        seen = set()
        unique = []
        for item in all_items:
            key = item.title[:60]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        unique.sort(key=lambda x: x.stars, reverse=True)
        return DailyDigest(domain=self.domain, items=unique[:20])

    async def _fetch_xueqiu_hot(self, client: httpx.AsyncClient) -> list[NewsItem]:
        try:
            resp = await client.get(
                XUEQIU_HOT_URL,
                params={"page": 1, "lastId": 0},
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": XUEQIU_REFERER,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            items_data = data.get("list", [])[:15]
        except Exception as e:
            print(f"  [雪球] 请求失败: {e}")
            return []

        items = []
        for it in items_data:
            data_obj = it.get("data", {})
            title = (data_obj.get("title") or data_obj.get("text") or "").strip()
            if not title:
                continue
            # Clean stock symbols like $BABA^ and $TSLA$
            title_clean = re.sub(r'\$[^)]*\^', '', title)
            title_clean = re.sub(r'\$[^)]*\$', '', title_clean)[:120]
            reply_count = data_obj.get("reply_count", 0)
            items.append(NewsItem(
                title=title_clean,
                url=f"https://xueqiu.com{data_obj.get('target', '')}",
                description=data_obj.get("description", "")[:200],
                source="雪球热帖",
                stars=reply_count,
            ))
        return items

    async def _fetch_cls_telegraph(self, client: httpx.AsyncClient) -> list[NewsItem]:
        try:
            resp = await client.get(
                CLS_TELEGRAPH_URL,
                params={"app": "CailianpressWeb", "os": "web", "sv": "8.4.6"},
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://www.cls.cn/telegraph",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            rolls = data.get("data", {}).get("roll_data", [])[:15]
        except Exception as e:
            print(f"  [财联社] 请求失败: {e}")
            return []

        items = []
        for roll in rolls:
            title = (roll.get("title") or roll.get("content") or "").strip()
            if not title:
                continue
            items.append(NewsItem(
                title=title[:120],
                url=f"https://www.cls.cn/detail/{roll.get('id', '')}",
                description=roll.get("brief", "")[:200],
                source="财联社电报",
                stars=roll.get("sharenum", 0),
            ))
        return items
