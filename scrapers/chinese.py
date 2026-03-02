"""中文源爬虫 — 少数派、V2EX、掘金、知乎"""
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from .base import BaseScraper, Article


class ChineseScraper(BaseScraper):
    SOURCE_NAME = "Chinese"

    def fetch(self) -> list[Article]:
        zh_config = self.config.get("chinese_sources", {})
        articles = []

        # RSS 源（少数派、InfoQ 等）
        rss_feeds = zh_config.get("rss", [])
        for feed in rss_feeds:
            items = self._fetch_rss(feed)
            articles.extend(items)

        # 需要爬取的站点
        for source in zh_config.get("crawl", []):
            source_type = source.get("type", "")
            if source_type == "v2ex":
                items = self._fetch_v2ex(source)
            elif source_type == "juejin":
                items = self._fetch_juejin(source)
            else:
                items = []
            articles.extend(items)

        print(f"[中文源] 共抓取 {len(articles)} 条")
        return articles

    def _fetch_rss(self, feed: dict) -> list[Article]:
        import feedparser
        from dateutil import parser as dateparser

        name = feed["name"]
        url = feed["url"]
        keywords = self.config.get("chinese_sources", {}).get("keywords", [])

        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"[中文RSS] {name} 失败: {e}")
            return []

        articles = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            # 关键词过滤
            if keywords and not any(kw.lower() in title.lower() for kw in keywords):
                content = entry.get("summary", "")
                if not any(kw.lower() in content.lower() for kw in keywords):
                    continue

            try:
                pub = dateparser.parse(entry.get("published", "")).replace(tzinfo=timezone.utc)
            except Exception:
                pub = datetime.now(timezone.utc)

            articles.append(Article(
                title=title.strip(),
                url=entry.get("link", ""),
                source=name,
                source_type="blog",
                published_at=pub,
                content=self._strip_html(entry.get("summary", ""))[:500],
                author=entry.get("author", ""),
                raw_id=self._make_raw_id(name, entry.get("id", entry.get("link", ""))),
                language="zh",
            ))

        return articles

    def _fetch_v2ex(self, source: dict) -> list[Article]:
        """抓取 V2EX Claude 节点"""
        url = source["url"]
        resp = self.safe_request(url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        articles = []

        for topic in soup.select(".cell.item")[:30]:
            title_el = topic.select_one(".item_title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")

            member_el = topic.select_one(".topic_info strong a")
            author = member_el.get_text(strip=True) if member_el else ""

            count_el = topic.select_one(".count_livid")
            replies = int(count_el.get_text(strip=True)) if count_el else 0

            articles.append(Article(
                title=title,
                url=f"https://www.v2ex.com{href}" if href.startswith("/") else href,
                source="V2EX",
                source_type="community",
                published_at=datetime.now(timezone.utc),
                author=author,
                comments=replies,
                raw_id=self._make_raw_id("v2ex", href),
                language="zh",
            ))

        return articles

    def _fetch_juejin(self, source: dict) -> list[Article]:
        """抓取掘金 Claude 标签文章（使用掘金 API）"""
        # 掘金提供了非官方 JSON API
        api_url = "https://api.juejin.cn/tag_api/v1/query_tag_detail"
        # 掘金 Claude 标签 ID 需要先查
        tag_search = "https://api.juejin.cn/tag_api/v1/query_tag_list"

        try:
            import requests
            # 搜索标签
            keywords = self.config.get("chinese_sources", {}).get("keywords", ["Claude"])
            articles = []

            for keyword in keywords[:2]:
                resp = requests.post(
                    "https://api.juejin.cn/search_api/v1/article/new_search",
                    json={
                        "key_word": keyword,
                        "search_type": "0",
                        "id_type": 0,
                        "cursor": "0",
                        "limit": 20,
                        "had_verify": 1,
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )
                data = resp.json()
                for item in data.get("data", []):
                    info = item.get("article_info", {})
                    user = item.get("author_user_info", {})
                    articles.append(Article(
                        title=info.get("title", ""),
                        url=f"https://juejin.cn/post/{info.get('article_id', '')}",
                        source="掘金",
                        source_type="blog",
                        published_at=datetime.fromtimestamp(
                            int(info.get("ctime", 0)), tz=timezone.utc
                        ),
                        content=info.get("brief_content", "")[:300],
                        author=user.get("user_name", ""),
                        score=info.get("digg_count", 0),
                        comments=info.get("comment_count", 0),
                        raw_id=self._make_raw_id("juejin", info.get("article_id", "")),
                        language="zh",
                    ))
        except Exception as e:
            print(f"[掘金] 抓取失败: {e}")
            return []

        return articles

    def _strip_html(self, text: str) -> str:
        if not text:
            return ""
        return BeautifulSoup(text, "lxml").get_text(separator=" ", strip=True)
