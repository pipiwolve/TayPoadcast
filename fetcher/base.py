"""Base classes for domain-specific fetchers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NewsItem:
    title: str
    url: str
    description: str
    source: str
    stars: int = 0
    language: str = ""

    def summary(self) -> str:
        return f"[{self.source}] {self.title} — {self.description}"


@dataclass
class DailyDigest:
    domain: str = "general"
    items: list[NewsItem] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        lines = []
        for i, item in enumerate(self.items, 1):
            lines.append(f"{i}. [{item.source}] {item.title}")
            if item.language:
                lines.append(f"   语言: {item.language}")
            if item.stars:
                lines.append(f"   热度: ⭐ {item.stars}")
            if item.description:
                lines.append(f"   简介: {item.description}")
            lines.append(f"   链接: {item.url}")
        lines.append(f"\n共 {len(self.items)} 条新闻，请从中挑选最具讨论价值的项目深度展开。")
        return "\n".join(lines)


class BaseFetcher(ABC):
    """Abstract base for domain-specific news fetchers."""

    domain: str = "general"

    @abstractmethod
    async def fetch(self) -> DailyDigest:
        ...
