"""内容处理流水线：去重 → 过滤 → Claude 分析 → 分类 → 置顶"""
import json
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from scrapers.base import Article
from processor.claude_cli import analyze_article, generate_daily_summary


DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SEEN_IDS_FILE = DATA_DIR / "seen_ids.json"
PINNED_FILE = DATA_DIR / "pinned.json"


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

        # 8. 处理置顶：新发现的经典内容写入 pinned.json
        self._update_pinned(articles)

        # 9. 保存处理后数据
        self._save_processed(articles, today)

        # 10. 更新已见 ID
        self._update_seen_ids(articles)

        pinned_count = sum(1 for a in articles if a.is_pinned)
        print(f"=== 流水线完成 | 最终 {len(articles)} 条，{pinned_count} 条置顶 ===\n")
        return articles

    def _deduplicate(self, articles: list[Article]) -> list[Article]:
        """基于 raw_id + URL + 标题相似度去重"""
        seen_ids = self._load_seen_ids()
        # 置顶文章的 ID 不参与去重（允许重新出现）
        pinned_ids = self._load_pinned_ids()

        seen_urls = set()
        seen_title_hashes = set()
        unique = []

        for article in articles:
            # 置顶文章跳过历史去重
            if article.raw_id not in pinned_ids and article.raw_id in seen_ids:
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
            "gpt", "workflow", "prompt", "模型", "人工智能",
            "mcp", "agent", "copilot", "cursor", "coding assistant",
        ]

        for article in articles:
            text = (article.title + " " + article.content).lower()

            # 排除垃圾内容
            if any(kw in text for kw in exclude_keywords):
                continue

            # 官方/SDK/学术来源直接通过，不做关键词过滤
            if article.source_type in ("official", "research"):
                filtered.append(article)
                continue

            # 其他来源需要包含相关关键词
            if any(kw in text for kw in required_keywords):
                filtered.append(article)

        return filtered

    def _claude_analyze(self, articles: list[Article]) -> list[Article]:
        """调用 Claude CLI 分析每篇文章（并发执行，带总体超时保护）"""
        concurrency = self.proc_config.get("claude_concurrency", 3)
        max_total_seconds = 600  # 10 分钟总超时
        total = len(articles)
        analyzed = []
        start_time = time.monotonic()

        def _process_one(idx_article):
            idx, article = idx_article
            print(f"  [{idx+1}/{total}] 分析: {article.title[:50]}...")
            result = analyze_article(article.title, article.content, article.source)
            return idx, article, result

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(_process_one, (i, a)) for i, a in enumerate(articles)]
            for future in as_completed(futures):
                # 检查总超时
                elapsed = time.monotonic() - start_time
                if elapsed > max_total_seconds:
                    print(f"  [超时] Claude 分析已运行 {elapsed:.0f}s，跳过剩余文章，使用规则评分")
                    for f in futures:
                        f.cancel()
                    break

                try:
                    _, article, result = future.result(timeout=60)
                except Exception as e:
                    print(f"  [分析错误] {e}")
                    continue

                if result:
                    if not result.get("is_relevant", True):
                        print(f"    → 不相关，跳过")
                        continue
                    article.summary_zh = result.get("summary_zh", "")
                    article.tags = result.get("tags", [])
                    article.quality_score = float(result.get("quality_score", 5.0))
                    article.category = result.get("category", "frontier")
                    # 置顶判断
                    if result.get("should_pin"):
                        article.is_pinned = True
                        article.pin_reason = result.get("pin_reason", "")
                        print(f"    📌 推荐置顶: {article.pin_reason}")
                else:
                    # Claude CLI 不可用时的降级策略
                    article.quality_score = self._rule_based_score(article)
                    article.summary_zh = article.content[:150] if article.content else article.title

                if article.quality_score >= self.min_quality:
                    analyzed.append(article)
                else:
                    print(f"    → 质量评分 {article.quality_score:.1f} 低于阈值，跳过")

        # 超时后，对未分析的文章使用规则评分
        if time.monotonic() - start_time > max_total_seconds:
            analyzed_ids = {id(a) for a in analyzed}
            for article in articles:
                if id(article) not in analyzed_ids:
                    article.quality_score = self._rule_based_score(article)
                    article.summary_zh = article.content[:150] if article.content else article.title
                    if article.quality_score >= self.min_quality:
                        analyzed.append(article)

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
            "research": 2.5,
            "blog": 1.5,
            "newsletter": 1.5,
            "news": 1.2,
            "community": 1.0,
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

    # ── 置顶管理 ──────────────────────────────────────

    def _load_pinned(self) -> list[dict]:
        """加载已置顶文章"""
        if PINNED_FILE.exists():
            with open(PINNED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _load_pinned_ids(self) -> set:
        return {p.get("raw_id", "") for p in self._load_pinned()}

    def _update_pinned(self, articles: list[Article]):
        """将新发现的经典内容追加到 pinned.json，最多保留 30 条"""
        pinned = self._load_pinned()
        pinned_urls = {p.get("url", "") for p in pinned}

        new_pins = [a for a in articles if a.is_pinned and a.url not in pinned_urls]

        for article in new_pins:
            pinned.append({
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "source_type": article.source_type,
                "summary_zh": article.summary_zh,
                "pin_reason": article.pin_reason,
                "quality_score": article.quality_score,
                "score": article.score,
                "tags": article.tags,
                "pinned_at": datetime.now(timezone.utc).isoformat(),
                "raw_id": article.raw_id,
                "author": article.author,
                "language": article.language,
            })
            print(f"  📌 新增置顶: {article.title[:60]}")

        # 按 quality_score 降序，保留前 30
        pinned.sort(key=lambda p: p.get("quality_score", 0), reverse=True)
        pinned = pinned[:30]

        with open(PINNED_FILE, "w", encoding="utf-8") as f:
            json.dump(pinned, f, ensure_ascii=False, indent=2, default=str)

        if new_pins:
            print(f"  📌 置顶库: 共 {len(pinned)} 条（新增 {len(new_pins)} 条）")

        # 标记所有已置顶的文章（包括之前已在库中的）
        for article in articles:
            if article.url in {p["url"] for p in pinned}:
                article.is_pinned = True

    # ── 数据保存 ──────────────────────────────────────

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
