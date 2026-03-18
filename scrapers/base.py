"""所有爬虫的基类，定义统一的数据结构"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class Article:
    """统一的内容条目格式"""
    # 必填
    title: str
    url: str
    source: str          # 来源平台，如 "HackerNews", "X", "Reddit"
    source_type: str     # 来源类型：official / community / news / blog / chinese

    # 时间
    published_at: Optional[datetime] = None

    # 内容
    content: str = ""    # 原文摘要或正文片段
    author: str = ""
    author_url: str = ""

    # 互动数据（用于评分）
    score: int = 0       # 点赞/upvote/star 数
    comments: int = 0
    shares: int = 0

    # 分类（由 processor 填充）
    tags: list = field(default_factory=list)
    quality_score: float = 0.0   # 0-10
    summary_zh: str = ""         # Claude CLI 生成的中文摘要
    category: str = ""           # frontier / stable
    is_frontier: bool = True

    # 元数据
    language: str = "en"         # en / zh
    raw_id: str = ""             # 原平台 ID，用于去重

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.published_at:
            d["published_at"] = self.published_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        if d.get("published_at") and isinstance(d["published_at"], str):
            d["published_at"] = datetime.fromisoformat(d["published_at"])
        return cls(**d)


class BaseScraper:
    """爬虫基类"""
    SOURCE_NAME = "unknown"

    def __init__(self, config: dict):
        self.config = config
        self.articles: list[Article] = []

    def fetch(self) -> list[Article]:
        """执行抓取，返回文章列表（子类实现）"""
        raise NotImplementedError

    def _make_raw_id(self, *parts) -> str:
        """生成去重 ID"""
        return f"{self.SOURCE_NAME}::" + "::".join(str(p) for p in parts)

    @staticmethod
    def safe_request(url: str, headers: dict = None, timeout: int = 10):
        """带重试的 HTTP 请求"""
        import requests
        from tenacity import retry, stop_after_attempt, wait_exponential
        headers = headers or {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            print(f"[{url}] 请求失败: {e}")
            return None
