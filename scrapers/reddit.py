"""Reddit 爬虫 — 使用 PRAW（需要免费的 Reddit API 应用）"""
import os
from datetime import datetime, timezone
from .base import BaseScraper, Article


class RedditScraper(BaseScraper):
    SOURCE_NAME = "Reddit"

    def fetch(self) -> list[Article]:
        try:
            import praw
        except ImportError:
            print("[Reddit] 未安装 praw，跳过")
            return []

        cfg = self.config.get("reddit", {})
        client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
        client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()

        if not client_id or not client_secret:
            print("[Reddit] 未配置 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET，跳过（只读模式已被 Reddit 封锁）")
            return []

        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=cfg.get("user_agent", "ClaudeNotice/1.0"),
            )
            return self._fetch_with_praw(reddit, cfg)
        except Exception as e:
            print(f"[Reddit] PRAW 失败: {e}")
            return self._fetch_readonly(cfg)

    def _fetch_with_praw(self, reddit, cfg: dict) -> list[Article]:
        """使用 PRAW 正式 API 抓取"""
        articles = []
        subreddits = cfg.get("subreddits", [])
        keywords = cfg.get("keywords", [])
        min_score = cfg.get("min_score", 20)
        limit = cfg.get("post_limit", 50)

        for sub_name in subreddits:
            try:
                sub = reddit.subreddit(sub_name)
                for post in sub.hot(limit=limit):
                    if post.score < min_score:
                        continue
                    text = post.title.lower()
                    if not any(kw.lower() in text for kw in keywords):
                        # 只有明确包含关键词的才要
                        if sub_name not in ["ClaudeAI"]:
                            continue

                    articles.append(self._post_to_article(post, sub_name))
                print(f"[Reddit] r/{sub_name}: {sum(1 for a in articles if sub_name in a.raw_id)} 条")
            except Exception as e:
                print(f"[Reddit] r/{sub_name} 失败: {e}")

        return articles

    def _fetch_readonly(self, cfg: dict) -> list[Article]:
        """不需要认证的只读接口（速率限制较低）"""
        import requests
        articles = []
        subreddits = cfg.get("subreddits", ["ClaudeAI"])
        min_score = cfg.get("min_score", 20)

        for sub_name in subreddits:
            url = f"https://www.reddit.com/r/{sub_name}/hot.json?limit=25"
            resp = self.safe_request(url, headers={"User-Agent": "ClaudeNotice/1.0"})
            if not resp:
                continue
            try:
                data = resp.json()
                for item in data.get("data", {}).get("children", []):
                    post = item.get("data", {})
                    if post.get("score", 0) < min_score:
                        continue
                    articles.append(Article(
                        title=post.get("title", ""),
                        url=f"https://reddit.com{post.get('permalink', '')}",
                        source=f"r/{sub_name}",
                        source_type="community",
                        published_at=datetime.fromtimestamp(
                            post.get("created_utc", 0), tz=timezone.utc
                        ),
                        content=post.get("selftext", "")[:500],
                        author=post.get("author", ""),
                        score=post.get("score", 0),
                        comments=post.get("num_comments", 0),
                        raw_id=self._make_raw_id(post.get("id", "")),
                    ))
            except Exception as e:
                print(f"[Reddit readonly] r/{sub_name} 解析失败: {e}")

        print(f"[Reddit readonly] 共 {len(articles)} 条")
        return articles

    def _post_to_article(self, post, sub_name: str) -> Article:
        return Article(
            title=post.title,
            url=f"https://reddit.com{post.permalink}",
            source=f"r/{sub_name}",
            source_type="community",
            published_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
            content=(post.selftext or "")[:500],
            author=str(post.author) if post.author else "",
            score=post.score,
            comments=post.num_comments,
            raw_id=self._make_raw_id(post.id),
        )
