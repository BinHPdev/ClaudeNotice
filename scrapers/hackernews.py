"""Hacker News 爬虫 — 使用 Algolia HN API（免费无需认证）"""
import requests
from datetime import datetime, timezone
from .base import BaseScraper, Article


HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsScraper(BaseScraper):
    SOURCE_NAME = "HackerNews"

    def fetch(self) -> list[Article]:
        hn_config = self.config.get("hackernews", {})
        keywords = hn_config.get("keywords", ["claude", "anthropic"])
        min_points = hn_config.get("min_points", 30)
        limit = hn_config.get("stories_limit", 100)

        articles = []
        seen_ids = set()

        for keyword in keywords:
            items = self._search(keyword, min_points, limit // len(keywords))
            for item in items:
                if item.raw_id not in seen_ids:
                    seen_ids.add(item.raw_id)
                    articles.append(item)

        print(f"[HN] 共抓取 {len(articles)} 条")
        return articles

    def _search(self, query: str, min_points: int, limit: int) -> list[Article]:
        try:
            resp = requests.get(HN_SEARCH_URL, params={
                "query": query,
                "tags": "story",
                "numericFilters": f"points>={min_points}",
                "hitsPerPage": limit,
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[HN] 搜索 '{query}' 失败: {e}")
            return []

        articles = []
        for hit in data.get("hits", []):
            story_id = hit.get("objectID", "")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"

            articles.append(Article(
                title=hit.get("title", "").strip(),
                url=url,
                source="Hacker News",
                source_type="community",
                published_at=datetime.fromtimestamp(
                    hit.get("created_at_i", 0), tz=timezone.utc
                ),
                content=hit.get("story_text", "") or "",
                author=hit.get("author", ""),
                author_url=f"https://news.ycombinator.com/user?id={hit.get('author', '')}",
                score=hit.get("points", 0),
                comments=hit.get("num_comments", 0),
                raw_id=self._make_raw_id(story_id),
            ))

        return articles
