"""通过 Claude Code CLI 处理内容

认证优先级（CLI 自行决定）：
  1. CLAUDE_CODE_OAUTH_TOKEN —— `claude setup-token` 生成的长期 token，走订阅额度。
     self-hosted runner 必须用这个：runner 的 LaunchAgent 带 SessionCreate=true，
     跑在独立 security session 里，读不到登录钥匙串中的 Claude Code-credentials，
     所以本机交互式登录态对定时任务无效（2026-05 起静默降级两个月的根因）。
  2. 本机登录态 —— 仅本地手动运行时可用。
"""
import os
import subprocess
import json
from dataclasses import dataclass, field
from typing import Optional


# CLI 每次调用都会加载插件 / hooks / skills / MCP / CLAUDE.md，
# 对"打分 + 两三句摘要"这种一次性分类任务纯属浪费（每天 100 次 × 全套开销）。
# 下面这组参数把会话裁到最小：
#   --strict-mcp-config       不加载任何 MCP server（未配 --mcp-config 即为空集）
#   --disable-slash-commands  不加载 skills
#   --no-session-persistence  不为每次调用各写一份会话文件
# 注意：不能用 --bare。它更彻底，但会强制"只认 ANTHROPIC_API_KEY"，
# 与订阅制的 CLAUDE_CODE_OAUTH_TOKEN 互斥。
_LEAN_FLAGS = [
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--no-session-persistence",
]

# 覆盖默认的 Claude Code 系统提示词，省掉几千 token 的 agent harness 上下文
_SYSTEM_PROMPT = "你是内容分析助手。严格按用户要求的格式输出，不要有任何多余的解释、前缀或后缀。"

# 认证失效的特征串。CLI 未登录时 rc=1，且把提示写在 stdout 而不是 stderr
# （例：stdout='Not logged in · Please run /login'），所以两个流都要查。
_AUTH_FAIL_MARKERS = (
    "not logged in",
    "please run /login",
    "invalid api key",
    "authentication_error",
    "oauth token",
)

# 可选：指定模型（如 "haiku" / "sonnet"）。留空则用 CLI 默认模型。
# 订阅制下这不影响账单，但影响额度消耗速度。
_MODEL = os.environ.get("CLAUDE_NOTICE_MODEL", "").strip()


@dataclass
class CallStats:
    """记录本次运行的调用结果，供上层判断是否发生大面积降级。

    存在的理由：此前每篇文章分析失败都只是 print 一行然后静默降级成规则评分，
    job 照样 exit 0。结果 100/100 全失败也报 success，持续两个月无人发现。
    """
    ok: int = 0
    failed: int = 0
    auth_failed: int = 0
    reasons: dict = field(default_factory=dict)

    def record_ok(self) -> None:
        self.ok += 1

    def record_fail(self, reason: str, is_auth: bool = False) -> None:
        self.failed += 1
        if is_auth:
            self.auth_failed += 1
        self.reasons[reason] = self.reasons.get(reason, 0) + 1

    @property
    def total(self) -> int:
        return self.ok + self.failed

    @property
    def ok_ratio(self) -> float:
        return self.ok / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "failed": self.failed,
            "auth_failed": self.auth_failed,
            "total": self.total,
            "ok_ratio": round(self.ok_ratio, 4),
            "reasons": self.reasons,
        }


STATS = CallStats()


def _run_cli(prompt: str, timeout: int) -> tuple[Optional[str], Optional[str], bool]:
    """执行一次 CLI 调用。

    返回 (输出文本, 失败原因, 是否认证问题)。成功时失败原因为 None。
    """
    cmd = ["claude", "-p", prompt, "--system-prompt", _SYSTEM_PROMPT, *_LEAN_FLAGS]
    if _MODEL:
        cmd += ["--model", _MODEL]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"超时(>{timeout}s)", False
    except FileNotFoundError:
        return None, "未找到 claude 命令", False
    except Exception as e:
        return None, f"异常: {e}", False

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    is_auth = any(m in f"{stdout}\n{stderr}".lower() for m in _AUTH_FAIL_MARKERS)

    if result.returncode != 0:
        if is_auth:
            return None, "认证失效", True
        return None, f"rc={result.returncode} stderr={stderr[:200]!r} stdout={stdout[:200]!r}", False

    if not stdout:
        # rc=0 但无输出。已知触发场景：在 Claude Code 会话内嵌套调用 CLI。
        # 旧代码把它和"正常返回空串"混为一谈，直接静默降级。
        return None, "rc=0 但输出为空（可能是嵌套会话）", False

    return stdout, None, False


def call_claude(prompt: str, input_text: str = "", timeout: int = 30) -> Optional[str]:
    """调用 Claude Code CLI，失败返回 None 并计入 STATS。"""
    full_prompt = prompt
    if input_text:
        full_prompt = f"{prompt}\n\n---内容---\n{input_text}"

    output, reason, is_auth = _run_cli(full_prompt, timeout)

    if reason:
        print(f"[Claude CLI] 失败: {reason}")
        STATS.record_fail(reason if is_auth else reason.split(" ")[0], is_auth)
        return None

    STATS.record_ok()
    return output


def healthcheck(timeout: int = 60) -> tuple[bool, str]:
    """真实发一次最小调用验证认证是否可用。

    比 `claude --version` 有意义得多——版本号在未登录时照样打印，
    这正是过去两个月健康检查全绿但分析全挂的原因。
    不计入 STATS。
    """
    output, reason, is_auth = _run_cli("回复 OK，不要有其他内容。", timeout)

    if reason:
        hint = "（需要配置 CLAUDE_CODE_OAUTH_TOKEN）" if is_auth else ""
        return False, f"{reason}{hint}"

    return True, f"认证正常，模型响应: {output[:50]!r}"


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
