#!/usr/bin/env python3
"""
ClaudeNotice — 主入口
用法:
  python main.py          # 全量运行（爬取 + 处理 + 生成网站）
  python main.py scrape   # 只爬取数据
  python main.py process  # 只处理（需已有 raw 数据）
  python main.py generate # 只生成网站（需已有 processed 数据）
  python main.py serve    # 本地预览网站
"""
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from rich.console import Console
from rich.panel import Panel
from rich.progress import track

console = Console()


def load_config() -> dict:
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_scrape(config: dict):
    """运行所有爬虫，保存原始数据"""
    from scrapers import (
        RssScraper, GithubScraper, HackerNewsScraper,
        RedditScraper, TwitterScraper, ChineseScraper,
    )

    scrapers = [
        ("RSS / 博客 / 新闻", RssScraper(config)),
        ("Hacker News",       HackerNewsScraper(config)),
        ("GitHub",            GithubScraper(config)),
        ("Reddit",            RedditScraper(config)),
        ("X (Twitter)",       TwitterScraper(config)),
        ("中文源",             ChineseScraper(config)),
    ]

    all_articles = []
    for name, scraper in scrapers:
        console.print(f"\n[bold cyan]→ {name}[/]")
        try:
            articles = scraper.fetch()
            all_articles.extend(articles)
            console.print(f"  [green]✓ {len(articles)} 条[/]")
        except Exception as e:
            console.print(f"  [red]✗ 失败: {e}[/]")

    console.print(f"\n[bold]共抓取 {len(all_articles)} 条原始数据[/]")
    return all_articles


def cmd_process(config: dict, articles=None):
    """处理内容（Claude CLI 分析 + 分类）"""
    from processor import ProcessingPipeline

    if articles is None:
        # 从最新 raw 文件加载
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw_path = Path(f"data/raw/{today}.json")
        if not raw_path.exists():
            console.print(f"[red]找不到 {raw_path}，请先运行 scrape[/]")
            sys.exit(1)
        from scrapers.base import Article
        with open(raw_path) as f:
            articles = [Article.from_dict(d) for d in json.load(f)]

    pipeline = ProcessingPipeline(config)
    processed = pipeline.run(articles)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = pipeline.generate_summary(processed, today)

    # 保存摘要
    Path("data/processed/daily_summary.txt").write_text(summary, encoding="utf-8")

    return processed, summary


def cmd_generate(config: dict, articles=None, summary: str = ""):
    """生成静态网站"""
    from generator import SiteGenerator

    gen = SiteGenerator(config)

    if articles is None:
        articles = SiteGenerator.load_from_file(config)
        if not summary:
            summary_path = Path("data/processed/daily_summary.txt")
            summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""

    gen.generate(articles, daily_summary=summary)
    console.print("\n[bold green]✓ 网站生成完成[/] → site/index.html")


def cmd_serve():
    """本地预览"""
    import http.server
    import socketserver
    import webbrowser
    import os

    os.chdir("site")
    port = 8080
    console.print(f"\n[bold]本地预览: http://localhost:{port}[/]")
    console.print("按 Ctrl+C 停止\n")
    webbrowser.open(f"http://localhost:{port}")

    with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    console.print(Panel.fit(
        f"[bold purple]⚡ ClaudeNotice[/]\n[dim]{datetime.now().strftime('%Y-%m-%d %H:%M')}[/]",
        border_style="purple",
    ))

    config = load_config()

    if cmd == "scrape":
        cmd_scrape(config)

    elif cmd == "process":
        cmd_process(config)

    elif cmd == "generate":
        cmd_generate(config)

    elif cmd == "serve":
        cmd_serve()

    elif cmd in ("all", "run"):
        # 全量运行
        console.print("\n[bold]第 1 步: 爬取数据[/]")
        articles = cmd_scrape(config)

        console.print("\n[bold]第 2 步: 处理内容（Claude CLI）[/]")
        processed, summary = cmd_process(config, articles)

        console.print("\n[bold]第 3 步: 生成网站[/]")
        cmd_generate(config, processed, summary)

        console.print("\n[bold green]✅ 全部完成！[/]")
        console.print("  运行 [cyan]python main.py serve[/] 本地预览")
        console.print("  运行 [cyan]git push[/] 发布到 GitHub Pages")

    else:
        console.print(f"[red]未知命令: {cmd}[/]")
        console.print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
