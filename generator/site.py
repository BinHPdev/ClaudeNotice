"""静态网站生成器 — 用 Jinja2 渲染 HTML"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from scrapers.base import Article

try:
    import markdown as md_lib
    _MD_AVAILABLE = True
except ImportError:
    _MD_AVAILABLE = False


TEMPLATE_DIR = Path("generator/templates")
SITE_DIR = Path("docs")


class SiteGenerator:
    def __init__(self, config: dict):
        self.config = config
        self.site_config = config.get("site", {})
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )
        self.env.filters["timeago"] = self._timeago_filter
        self.env.filters["source_icon"] = self._source_icon_filter

    def generate(self, articles: list[Article], daily_summary: str = ""):
        SITE_DIR.mkdir(parents=True, exist_ok=True)

        # Claude Code 官方动态（置顶专区）
        official_articles = [a for a in articles if a.source_type == "official"]
        non_official = [a for a in articles if a.source_type != "official"]

        frontier = [a for a in non_official if a.is_frontier]
        stable = [a for a in non_official if not a.is_frontier]

        # 按标签分组（用于筛选）
        all_tags = sorted(set(tag for a in articles for tag in a.tags))

        # 来源统计
        sources = {}
        for a in articles:
            sources[a.source] = sources.get(a.source, 0) + 1

        # 渲染 AWESOME-CLAUDE-CODE.md → HTML
        awesome_html = self._render_awesome_md()

        now = datetime.now(timezone.utc)
        github_repo = self.site_config.get("github_repo", "")

        template = self.env.get_template("index.html")
        html = template.render(
            site_title=self.site_config.get("title", "ClaudeNotice"),
            site_description=self.site_config.get("description", ""),
            updated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
            updated_at_zh=self._format_date_zh(now),
            daily_summary=daily_summary,
            official_articles=official_articles,
            frontier_articles=frontier,
            stable_articles=stable,
            all_tags=all_tags,
            sources=sources,
            total_count=len(articles),
            frontier_count=len(frontier),
            stable_count=len(stable),
            official_count=len(official_articles),
            awesome_html=awesome_html,
            github_repo=github_repo,
        )

        output_path = SITE_DIR / "index.html"
        output_path.write_text(html, encoding="utf-8")
        print(f"网站已生成: {output_path} ({len(html)//1024}KB)")

        # 复制静态资源
        self._copy_static()

    def _render_awesome_md(self) -> str:
        """读取 AWESOME-CLAUDE-CODE.md 并转换为 HTML"""
        md_path = Path("AWESOME-CLAUDE-CODE.md")
        if not md_path.exists():
            return "<p>精选资源文件暂未生成。</p>"
        content = md_path.read_text(encoding="utf-8")
        if _MD_AVAILABLE:
            return md_lib.markdown(
                content,
                extensions=["fenced_code", "tables", "toc"],
            )
        # 极简 fallback：wrap in <pre>
        import html as html_lib
        return f"<pre style='white-space:pre-wrap;font-size:.85rem'>{html_lib.escape(content)}</pre>"

    def _copy_static(self):
        static_src = TEMPLATE_DIR / "static"
        static_dst = SITE_DIR / "static"
        if static_src.exists():
            shutil.copytree(static_src, static_dst, dirs_exist_ok=True)

    @staticmethod
    def _timeago_filter(dt) -> str:
        if not dt:
            return ""
        if isinstance(dt, str):
            try:
                from dateutil import parser
                dt = parser.parse(dt)
            except Exception:
                return dt

        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        diff = now - dt
        seconds = diff.total_seconds()

        if seconds < 3600:
            m = int(seconds / 60)
            return f"{m} 分钟前" if m > 0 else "刚刚"
        elif seconds < 86400:
            h = int(seconds / 3600)
            return f"{h} 小时前"
        elif seconds < 86400 * 7:
            d = int(seconds / 86400)
            return f"{d} 天前"
        else:
            return dt.strftime("%m月%d日")

    @staticmethod
    def _source_icon_filter(source: str) -> str:
        icons = {
            "Claude Code Releases": "⚡",
            "Anthropic SDK": "◆",
            "PyPI": "🐍",
            "Anthropic News": "◆",
            "Anthropic Engineering": "◆",
            "Anthropic Research": "◆",
            "OpenAI": "○",
            "HuggingFace": "🤗",
            "arXiv": "📄",
            "X (Twitter)": "𝕏",
            "Hacker News": "Y",
            "GitHub": "⑂",
            "YouTube": "▶",
            "Ben's Bites": "🍔",
            "Import AI": "📬",
            "掘金": "稀",
            "V2EX": "V",
            "少数派": "少",
            "Reddit": "🔴",
        }
        for key, icon in icons.items():
            if key in source:
                return icon
        return "◉"

    @staticmethod
    def _format_date_zh(dt: datetime) -> str:
        return dt.strftime("%Y年%m月%d日 %H:%M")

    @classmethod
    def load_from_file(cls, config: dict, date: str = "latest") -> list[Article]:
        """从处理后的 JSON 文件加载数据"""
        path = Path(f"data/processed/{date}.json")
        if not path.exists():
            print(f"找不到数据文件: {path}")
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Article.from_dict(d) for d in data]
