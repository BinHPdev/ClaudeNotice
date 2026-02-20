"""内容处理流水线：去重 → 过滤 → Claude 分析 → 分类"""
import json
import hashlib
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from scrapers.base import Article
from processor.claude_cli import analyze_article, generate_daily_summary


DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SEEN_IDS_FILE = DATA_DIR / "seen_ids.json"


class ProcessingPipeline:
    def __init__(self, config: dict):
        self.config = config
        self.proc_config = config.get("processing", {})
        self.frontier_days = self.proc_config.get("frontier_days", 7)
        self.min_quality = self.proc_config.get("min_quality_score", 5.0)
        self.max_items = self.proc_config.get("max_items_per_run", 100)

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, articles: list[Article]) -> list[Article]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        print(f"\n=== 处理流水线开始 | {len(articles)} 条原始数据 ===")

        # 1. 去重
        articles = self._deduplicate(articles)
        print(f"去重后: {len(articles)} 条")

        # 2. 保存原始数据
        self._save_raw(articles, today)

        # 3. 基本过滤（排除明显无关内容）
        articles = self._basic_filter(articles)
        print(f"基本过滤后: {len(articles)} 条")

        # 4. 限制处理数量
        articles = articles[:self.max_items]

        # 5. Claude CLI 智能分析
        articles = self._claude_analyze(articles)
        print(f"Claude 分析后: {len(articles)} 条有效内容")

        # 6. 分类：前沿 vs 成熟
        articles = self._classify_frontier(articles)

        # 7. 按质量评分排序
        articles.sort(key=lambda a: a.quality_score, reverse=True)

        # 8. 保存处理后数据
        self._save_processed(articles, today)

        # 9. 更新已见 ID
        self._update_seen_ids(articles)

        print(f"=== 流水线完成 | 最终 {len(articles)} 条 ===\n")
        return articles

    def _deduplicate(self, articles: list[Article]) -> list[Article]:
        """基于 raw_id + URL + 标题相似度去重"""
        seen_ids = self._load_seen_ids()
        seen_urls = set()
        seen_title_hashes = set()
        unique = []

        for article in articles:
            # 检查历史已见
            if article.raw_id in seen_ids:
                continue

            # URL 去重
            url_key = article.url.rstrip("/")
            if url_key in seen_urls:
                continue

            # 标题哈希去重（处理同一内容不同来源）
            title_hash = hashlib.md5(article.title[:50].lower().encode()).hexdigest()
            if title_hash in seen_title_hashes:
                continue

            seen_urls.add(url_key)
            seen_title_hashes.add(title_hash)
            unique.append(article)

        return unique

    def _basic_filter(self, articles: list[Article]) -> list[Article]:
        """过滤掉明显无关的内容（无需调用 Claude）"""
        filtered = []
        exclude_keywords = [
            "giveaway", "free iphone", "subscribe", "课程报名",
            "股价", "stock price", "earnings call"
        ]
        required_keywords = [
            "claude", "anthropic", "claude code", "ai", "llm",
            "gpt", "workflow", "prompt", "模型", "人工智能"
        ]

        for article in articles:
            text = (article.title + " " + article.content).lower()

            # 排除垃圾内容
            if any(kw in text for kw in exclude_keywords):
                continue

            # 官方来源直接通过
            if article.source_type == "official":
                filtered.append(article)
                continue

            # 其他来源需要包含相关关键词
            if any(kw in text for kw in required_keywords):
                filtered.append(article)

        return filtered

    def _claude_analyze(self, articles: list[Article]) -> list[Article]:
        """调用 Claude CLI 分析每篇文章"""
        analyzed = []
        total = len(articles)

        for i, article in enumerate(articles):
            print(f"  [{i+1}/{total}] 分析: {article.title[:50]}...")

            result = analyze_article(article.title, article.content, article.source)

            if result:
                # 过滤不相关内容
                if not result.get("is_relevant", True):
                    print(f"    → 不相关，跳过")
                    continue

                article.summary_zh = result.get("summary_zh", "")
                article.tags = result.get("tags", [])
                article.quality_score = float(result.get("quality_score", 5.0))
                article.category = result.get("category", "frontier")
            else:
                # Claude CLI 不可用时的降级策略
                article.quality_score = self._rule_based_score(article)
                article.summary_zh = article.content[:150] if article.content else article.title

            if article.quality_score >= self.min_quality:
                analyzed.append(article)
            else:
                print(f"    → 质量评分 {article.quality_score:.1f} 低于阈值，跳过")

            # 避免调用过于频繁
            time.sleep(0.5)

        return analyzed

    def _classify_frontier(self, articles: list[Article]) -> list[Article]:
        """根据发布时间标记前沿/成熟"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.frontier_days)

        for article in articles:
            pub = article.published_at
            if pub and pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)

            if pub and pub >= cutoff:
                article.is_frontier = True
                if not article.category:
                    article.category = "frontier"
            else:
                article.is_frontier = False
                if not article.category:
                    article.category = "stable"

        return articles

    def _rule_based_score(self, article: Article) -> float:
        """Claude CLI 不可用时的规则评分"""
        score = 5.0

        # 来源权重
        source_weights = {
            "official": 3.0,
            "blog": 1.5,
            "community": 1.0,
            "news": 1.2,
        }
        score += source_weights.get(article.source_type, 0)

        # 互动数（归一化）
        if article.score > 500:
            score += 1.5
        elif article.score > 100:
            score += 1.0
        elif article.score > 20:
            score += 0.5

        return min(score, 10.0)

    def _save_raw(self, articles: list[Article], date: str):
        path = RAW_DIR / f"{date}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in articles], f, ensure_ascii=False, indent=2, default=str)
        print(f"原始数据已保存: {path}")

    def _save_processed(self, articles: list[Article], date: str):
        path = PROCESSED_DIR / f"{date}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in articles], f, ensure_ascii=False, indent=2, default=str)

        # 同时更新 latest.json（供生成器使用）
        latest_path = PROCESSED_DIR / "latest.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in articles], f, ensure_ascii=False, indent=2, default=str)

        print(f"处理后数据已保存: {path}")

    def _load_seen_ids(self) -> set:
        if SEEN_IDS_FILE.exists():
            with open(SEEN_IDS_FILE, "r") as f:
                data = json.load(f)
                return set(data.get("ids", []))
        return set()

    def _update_seen_ids(self, articles: list[Article]):
        seen = self._load_seen_ids()
        seen.update(a.raw_id for a in articles)
        # 只保留最近 5000 个（防止文件过大）
        ids_list = list(seen)[-5000:]
        with open(SEEN_IDS_FILE, "w") as f:
            json.dump({"ids": ids_list}, f)

    def generate_summary(self, articles: list[Article], date: str) -> str:
        """生成今日摘要导语"""
        summary_input = "\n".join(
            f"- {a.title} ({a.source})"
            for a in articles[:20]
        )
        return generate_daily_summary(summary_input, date)
