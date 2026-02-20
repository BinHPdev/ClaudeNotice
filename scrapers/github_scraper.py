"""GitHub 爬虫 — 抓取仓库、讨论、Trending"""
import requests
from datetime import datetime, timezone
from .base import BaseScraper, Article

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"  # 可选，提升速率限制


class GithubScraper(BaseScraper):
    SOURCE_NAME = "GitHub"

    def __init__(self, config: dict):
        super().__init__(config)
        import os
        token = os.getenv(GITHUB_TOKEN_ENV)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def fetch(self) -> list[Article]:
        gh_config = self.config.get("github", {})
        articles = []

        # 1. 按 topic 搜索仓库
        for topic in gh_config.get("topics", []):
            items = self._search_by_topic(topic, gh_config.get("min_stars", 10))
            articles.extend(items)

        # 2. 关键词搜索仓库/README
        for query in gh_config.get("search_queries", []):
            items = self._search_repos(query, gh_config.get("min_stars", 10))
            articles.extend(items)

        # 去重
        seen = set()
        unique = []
        for a in articles:
            if a.raw_id not in seen:
                seen.add(a.raw_id)
                unique.append(a)

        print(f"[GitHub] 共抓取 {len(unique)} 条")
        return unique

    def _search_by_topic(self, topic: str, min_stars: int) -> list[Article]:
        url = f"{GITHUB_API}/search/repositories"
        params = {
            "q": f"topic:{topic} stars:>={min_stars}",
            "sort": "updated",
            "per_page": 20,
        }
        return self._parse_repo_search(requests.get(url, headers=self.headers, params=params, timeout=15))

    def _search_repos(self, query: str, min_stars: int) -> list[Article]:
        url = f"{GITHUB_API}/search/repositories"
        params = {
            "q": f"{query} stars:>={min_stars}",
            "sort": "updated",
            "per_page": 15,
        }
        return self._parse_repo_search(requests.get(url, headers=self.headers, params=params, timeout=15))

    def _parse_repo_search(self, resp) -> list[Article]:
        try:
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[GitHub] 请求失败: {e}")
            return []

        articles = []
        for repo in data.get("items", []):
            updated = repo.get("updated_at", "")
            try:
                pub = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except Exception:
                pub = datetime.now(timezone.utc)

            articles.append(Article(
                title=f"[GitHub] {repo['full_name']} — {repo.get('description', '')[:100]}",
                url=repo["html_url"],
                source="GitHub",
                source_type="community",
                published_at=pub,
                content=repo.get("description", "") or "",
                author=repo.get("owner", {}).get("login", ""),
                author_url=repo.get("owner", {}).get("html_url", ""),
                score=repo.get("stargazers_count", 0),
                raw_id=self._make_raw_id(repo["id"]),
                tags=repo.get("topics", []),
            ))

        return articles
