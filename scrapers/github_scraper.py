"""GitHub 爬虫 — 仓库搜索 + Trending + 影响力综合评估"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from .base import BaseScraper, Article

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"


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

        tasks = []

        # 1. 按 topic 搜索仓库
        for topic in gh_config.get("topics", []):
            tasks.append(("topic", topic, gh_config.get("min_stars", 10)))

        # 2. 关键词搜索仓库
        for query in gh_config.get("search_queries", []):
            tasks.append(("query", query, gh_config.get("min_stars", 10)))

        # 3. Trending（最近 7 天新创建 + 高星）
        if gh_config.get("trending", True):
            tasks.append(("trending", None, None))

        # 4. 近期快速增长的仓库（created in last 30 days, sorted by stars）
        tasks.append(("rising", None, None))

        # 并发执行所有搜索
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            for task_type, param, min_stars in tasks:
                if task_type == "topic":
                    futures.append(executor.submit(self._search_by_topic, param, min_stars))
                elif task_type == "query":
                    futures.append(executor.submit(self._search_repos, param, min_stars))
                elif task_type == "trending":
                    futures.append(executor.submit(self._fetch_trending))
                elif task_type == "rising":
                    futures.append(executor.submit(self._fetch_rising_stars))

            for future in as_completed(futures, timeout=60):
                try:
                    articles.extend(future.result())
                except Exception as e:
                    print(f"[GitHub] 任务失败: {e}")

        # 去重
        seen = set()
        unique = []
        for a in articles:
            if a.raw_id not in seen:
                seen.add(a.raw_id)
                unique.append(a)

        # 按综合影响力排序
        unique.sort(key=lambda a: a.score, reverse=True)

        print(f"[GitHub] 共抓取 {len(unique)} 条")
        return unique

    def _search_by_topic(self, topic: str, min_stars: int) -> list[Article]:
        url = f"{GITHUB_API}/search/repositories"
        params = {
            "q": f"topic:{topic} stars:>={min_stars}",
            "sort": "updated",
            "per_page": 20,
        }
        return self._parse_repo_search(
            requests.get(url, headers=self.headers, params=params, timeout=10)
        )

    def _search_repos(self, query: str, min_stars: int) -> list[Article]:
        url = f"{GITHUB_API}/search/repositories"
        params = {
            "q": f"{query} stars:>={min_stars}",
            "sort": "updated",
            "per_page": 15,
        }
        return self._parse_repo_search(
            requests.get(url, headers=self.headers, params=params, timeout=10)
        )

    def _fetch_trending(self) -> list[Article]:
        """获取最近 7 天创建、与 AI/Claude 相关的高星仓库"""
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"{GITHUB_API}/search/repositories"

        all_articles = []
        queries = [
            f"claude created:>{since} stars:>=5",
            f"anthropic created:>{since} stars:>=5",
            f"ai agent created:>{since} stars:>=50",
            f"llm tool created:>{since} stars:>=30",
        ]

        for q in queries:
            try:
                resp = requests.get(url, headers=self.headers, params={
                    "q": q, "sort": "stars", "order": "desc", "per_page": 10,
                }, timeout=10)
                all_articles.extend(self._parse_repo_search(resp, source_label="GitHub Trending"))
            except Exception as e:
                print(f"[GitHub Trending] 查询失败: {e}")

        return all_articles

    def _fetch_rising_stars(self) -> list[Article]:
        """最近 30 天内创建的快速增长仓库"""
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        url = f"{GITHUB_API}/search/repositories"

        try:
            resp = requests.get(url, headers=self.headers, params={
                "q": f"claude OR anthropic OR claude-code created:>{since} stars:>=20",
                "sort": "stars",
                "order": "desc",
                "per_page": 15,
            }, timeout=10)
            return self._parse_repo_search(resp, source_label="GitHub Rising")
        except Exception as e:
            print(f"[GitHub Rising] 查询失败: {e}")
            return []

    def _parse_repo_search(self, resp, source_label: str = "GitHub") -> list[Article]:
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

            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)
            watchers = repo.get("watchers_count", 0)

            # 构建丰富的内容描述
            desc = repo.get("description", "") or ""
            lang = repo.get("language", "") or ""
            topics = repo.get("topics", [])

            content_parts = [desc]
            if lang:
                content_parts.append(f"Language: {lang}")
            content_parts.append(f"Stars: {stars} | Forks: {forks} | Watchers: {watchers}")
            if topics:
                content_parts.append(f"Topics: {', '.join(topics[:8])}")

            # 影响力综合评分：stars 为主，forks 和 watchers 加权
            influence_score = stars + forks * 2 + watchers

            articles.append(Article(
                title=f"[{source_label}] {repo['full_name']} — {desc[:100]}",
                url=repo["html_url"],
                source=source_label,
                source_type="community",
                published_at=pub,
                content="\n".join(content_parts),
                author=repo.get("owner", {}).get("login", ""),
                author_url=repo.get("owner", {}).get("html_url", ""),
                score=stars,
                comments=forks,  # 复用 comments 字段存 forks
                shares=watchers,  # 复用 shares 字段存 watchers
                raw_id=self._make_raw_id(repo["id"]),
                tags=topics[:5],
            ))

        return articles
