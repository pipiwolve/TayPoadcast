"""Fetcher package — pluggable domain modules."""

from fetcher.base import BaseFetcher, DailyDigest, NewsItem

__all__ = ["BaseFetcher", "DailyDigest", "NewsItem"]
