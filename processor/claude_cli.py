"""通过 Claude Code CLI 处理内容 — 无需 API Key"""
import subprocess
import json
import re
from typing import Optional


def call_claude(prompt: str, input_text: str = "", timeout: int = 30) -> Optional[str]:
    """
    调用本地 Claude Code CLI。
    需要在本机安装了 claude 命令（Claude Code 桌面版自带）。
    """
    try:
        full_prompt = prompt
        if input_text:
            full_prompt = f"{prompt}\n\n---内容---\n{input_text}"

        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"[Claude CLI] 错误: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print("[Claude CLI] 超时")
        return None
    except FileNotFoundError:
        print("[Claude CLI] 未找到 claude 命令，请确认 Claude Code 已安装")
        return None
    except Exception as e:
        print(f"[Claude CLI] 异常: {e}")
        return None


def analyze_article(title: str, content: str, source: str) -> Optional[dict]:
    """
    让 Claude 分析一篇文章，返回：
    - summary_zh: 中文摘要（2-3句）
    - tags: 相关标签列表
    - quality_score: 质量评分 0-10
    - category: frontier / stable
    - is_relevant: 是否与 Claude Code 使用相关
    """
    prompt = f"""你是一个 Claude Code / AI 技术内容筛选助手。

请分析以下来自「{source}」的文章，判断它是否与 Claude Code 使用、AI 编程工具、LLM 工作流、最佳实践相关。

请严格输出以下 JSON 格式，不要有任何多余文字：

{{
  "is_relevant": true/false,
  "summary_zh": "2-3句中文摘要，说明文章的核心价值",
  "tags": ["标签1", "标签2"],  // 从以下选择：CLAUDE.md、workflow、提效技巧、新功能、最佳实践、工具集成、案例分享、模型能力、提示工程、SDK更新、研究论文、GitHub热门、MCP
  "quality_score": 7.5,  // 0-10分，综合信息密度、实用性、新颖性
  "category": "frontier",  // frontier=7天内新内容/新技巧; stable=经过验证的成熟实践
  "should_pin": false,  // 是否值得「经典置顶」— 仅对具有长期参考价值的里程碑内容设为 true（如重大版本发布、开创性教程、权威最佳实践指南、高星开源工具）
  "pin_reason": ""  // 如 should_pin=true，用一句话说明为什么值得置顶
}}

文章标题：{title}
文章内容：{content[:800]}"""

    result = call_claude(prompt)
    if not result:
        return None

    # 提取 JSON
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        # 找第一个 { 到最后一个 } 之间的内容（处理 Claude 在 JSON 前后输出多余文字的情况）
        start = result.find('{')
        end = result.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(result[start:end + 1])
            except Exception:
                pass
    return None


def generate_daily_summary(articles_summary: str, date: str) -> str:
    """生成每日摘要（用于网站首页导语）"""
    prompt = f"""今天是 {date}，根据以下 Claude Code 相关资讯摘要，用3-4句话写一个简洁的"今日速览"导语，
突出最重要的动态和趋势，语气简练专业，输出纯文本：

{articles_summary[:2000]}"""

    return call_claude(prompt) or "今日内容已更新，请查看下方详情。"
