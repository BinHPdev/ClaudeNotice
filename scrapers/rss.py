"""RSS/Atom 源爬虫 — 覆盖博客、科技媒体、官方博客"""
import feedparser
from datetime import datetime, timezone
from dateutil import parser as dateparser
from .base import BaseScraper, Article


class RssScraper(BaseScraper):
    SOURCE_NAME = "rss"

    def fetch(self) -> list[Article]:
        articles = []
        rss_config = self.config.get("rss_feeds", {})

        all_feeds = []
        for category, feeds in rss_config.items():
            source_type = self._map_category(category)
            for feed in feeds:
                all_feeds.append((feed, source_type))

        # YouTube RSS
        for ch in self.config.get("youtube", {}).get("channels", []):
            tpl = self.config["youtube"].get(
                "rss_template",
                "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            )
            url = tpl.format(channel_id=ch["channel_id"])
            all_feeds.append(({"name": ch["name"], "url": url}, "video"))

        for feed_info, source_type in all_feeds:
            try:
                items = self._parse_feed(feed_info, source_type)
                articles.extend(items)
                print(f"[RSS] {feed_info['name']}: {len(items)} 条")
            except Exception as e:
                print(f"[RSS] {feed_info.get('name', '?')} 失败: {e}")

        return articles

    def _parse_feed(self, feed_info: dict, source_type: str) -> list[Article]:
        url = feed_info["url"]
        name = feed_info["name"]

        # Anthropic 官方博客需要 HTML 解析（非标准 RSS）
        if feed_info.get("type") == "html":
            return self._scrape_anthropic_html(url, name)

        parsed = feedparser.parse(url)
        articles = []

        for entry in parsed.entries:
            pub = self._parse_date(entry)
            content = (
                entry.get("summary", "")
                or entry.get("content", [{}])[0].get("value", "")
            )
            # 截断过长内容
            content = content[:2000] if content else ""

            articles.append(Article(
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                source=name,
                source_type=source_type,
                published_at=pub,
                content=self._strip_html(content),
                author=entry.get("author", ""),
                raw_id=self._make_raw_id(name, entry.get("id", entry.get("link", ""))),
                language="zh" if "中文" in name or "少数派" in name or "InfoQ" in name else "en",
            ))

        return articles

    def _scrape_anthropic_html(self, url: str, name: str) -> list[Article]:
        """专门解析 Anthropic 官方博客（HTML 页面）"""
        from bs4 import BeautifulSoup

        resp = self.safe_request(url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        articles = []

        # Anthropic 博客的文章卡片选择器
        for card in soup.select("a[href*='/news/'], a[href*='/research/']")[:20]:
            href = card.get("href", "")
            if not href or href in [u.url for u in articles]:
                continue

            full_url = f"https://www.anthropic.com{href}" if href.startswith("/") else href
            title = card.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            articles.append(Article(
                title=title,
                url=full_url,
                source=name,
                source_type="official",
                published_at=datetime.now(timezone.utc),
                raw_id=self._make_raw_id(name, href),
            ))

        return articles

    def _parse_date(self, entry) -> datetime:
        for field in ["published", "updated", "created"]:
            val = entry.get(f"{field}_parsed") or entry.get(field)
            if val:
                try:
                    if hasattr(val, "tm_year"):
                        import time
                        return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
                    return dateparser.parse(str(val)).replace(tzinfo=timezone.utc)
                except Exception:
                    pass
        return datetime.now(timezone.utc)

    def _strip_html(self, text: str) -> str:
        from bs4 import BeautifulSoup
        if not text:
            return ""
        return BeautifulSoup(text, "lxml").get_text(separator=" ", strip=True)[:1000]

    def _map_category(self, category: str) -> str:
        mapping = {
            "official": "official",
            "tech_news": "news",
            "high_quality_blogs": "blog",
            "developer_blogs": "blog",
        }
        return mapping.get(category, "news")
