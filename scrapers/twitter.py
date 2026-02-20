"""X (Twitter) 爬虫 — 通过 Nitter 镜像抓取（非官方，免费）"""
import re
import time
import random
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from .base import BaseScraper, Article


class TwitterScraper(BaseScraper):
    SOURCE_NAME = "X"

    # 公共 Nitter 实例列表（如失效可在 config.yml 中更新）
    DEFAULT_NITTER_INSTANCES = [
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.1d4.us",
        "https://nitter.cz",
    ]

    def fetch(self) -> list[Article]:
        tw_config = self.config.get("twitter", {})
        accounts = tw_config.get("accounts", [])
        keywords = tw_config.get("keywords", [])
        max_tweets = tw_config.get("max_tweets_per_account", 20)

        instances = tw_config.get("nitter_instances", self.DEFAULT_NITTER_INSTANCES)
        working_instance = self._find_working_instance(instances)

        if not working_instance:
            print("[X] 所有 Nitter 实例均不可用，跳过 X 抓取")
            return []

        print(f"[X] 使用 Nitter 实例: {working_instance}")
        articles = []
        seen_ids = set()

        # 1. 按账号抓取
        for account in accounts:
            tweets = self._fetch_account(working_instance, account, max_tweets, keywords)
            for t in tweets:
                if t.raw_id not in seen_ids:
                    seen_ids.add(t.raw_id)
                    articles.append(t)
            time.sleep(random.uniform(1.5, 3.0))  # 礼貌性延迟

        # 2. 按关键词搜索
        for keyword in keywords:
            tweets = self._search_keyword(working_instance, keyword, 20)
            for t in tweets:
                if t.raw_id not in seen_ids:
                    seen_ids.add(t.raw_id)
                    articles.append(t)
            time.sleep(random.uniform(1.0, 2.0))

        print(f"[X] 共抓取 {len(articles)} 条推文")
        return articles

    def _find_working_instance(self, instances: list) -> str | None:
        for instance in instances:
            try:
                resp = self.safe_request(f"{instance}/AnthropicAI", timeout=8)
                if resp and resp.status_code == 200 and "timeline" in resp.text:
                    return instance
            except Exception:
                pass
        return None

    def _fetch_account(self, instance: str, account: str, limit: int, filter_keywords: list) -> list[Article]:
        url = f"{instance}/{account}"
        resp = self.safe_request(url)
        if not resp:
            return []

        articles = []
        soup = BeautifulSoup(resp.text, "lxml")

        for tweet_div in soup.select(".timeline-item")[:limit]:
            article = self._parse_tweet(tweet_div, account, instance, filter_keywords)
            if article:
                articles.append(article)

        return articles

    def _search_keyword(self, instance: str, keyword: str, limit: int) -> list[Article]:
        url = f"{instance}/search"
        resp = self.safe_request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        # Nitter 搜索需要带参数
        import requests
        try:
            resp = requests.get(
                f"{instance}/search",
                params={"q": keyword, "f": "tweets"},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                timeout=12,
            )
        except Exception:
            return []

        if not resp or resp.status_code != 200:
            return []

        articles = []
        soup = BeautifulSoup(resp.text, "lxml")
        for tweet_div in soup.select(".timeline-item")[:limit]:
            article = self._parse_tweet(tweet_div, "", instance, [])
            if article:
                articles.append(article)

        return articles

    def _parse_tweet(self, div, account: str, instance: str, filter_keywords: list) -> Article | None:
        try:
            content_el = div.select_one(".tweet-content")
            if not content_el:
                return None
            content = content_el.get_text(strip=True)

            # 关键词过滤（账号模式下过滤低相关内容）
            if filter_keywords and account not in ["AnthropicAI"]:
                if not any(kw.lower() in content.lower() for kw in filter_keywords):
                    return None

            # 作者
            author_el = div.select_one(".username")
            author = author_el.get_text(strip=True).lstrip("@") if author_el else account

            # 链接
            link_el = div.select_one(".tweet-link")
            tweet_path = link_el.get("href", "") if link_el else ""
            tweet_url = f"https://twitter.com{tweet_path}" if tweet_path else ""

            # ID
            raw_id = tweet_path.split("/")[-1] if tweet_path else content[:30]

            # 时间
            time_el = div.select_one(".tweet-date a")
            pub = self._parse_tweet_time(time_el.get("title", "") if time_el else "")

            # 互动数
            stats = div.select(".icon-container")
            likes = self._extract_stat(stats, 2)
            retweets = self._extract_stat(stats, 1)

            return Article(
                title=content[:140],
                url=tweet_url,
                source="X (Twitter)",
                source_type="community",
                published_at=pub,
                content=content,
                author=f"@{author}",
                author_url=f"https://twitter.com/{author}",
                score=likes,
                shares=retweets,
                raw_id=self._make_raw_id(raw_id),
            )
        except Exception as e:
            return None

    def _extract_stat(self, containers, index: int) -> int:
        try:
            text = containers[index].get_text(strip=True)
            text = re.sub(r"[^\d]", "", text)
            return int(text) if text else 0
        except Exception:
            return 0

    def _parse_tweet_time(self, time_str: str) -> datetime:
        """解析 Nitter 时间格式如 'Feb 19, 2026 · 10:30 AM UTC'"""
        try:
            from dateutil import parser as dateparser
            return dateparser.parse(time_str).replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
