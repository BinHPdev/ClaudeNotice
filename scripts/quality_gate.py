#!/usr/bin/env python3
"""CI 质量门禁：Claude 分析大面积失败时把 job 标红。

放在发布之后运行 —— 内容照常上线（规则评分的结果也好过没有），
但 job 会变红并触发 GitHub 通知，避免 AI 分析全挂却报 success 的静默退化。
2026-05~07 就是因为缺这一环，规则评分跑了两个月无人察觉。

退出码：0 = 通过，1 = 大面积降级。
"""
import json
import sys
from pathlib import Path

STATS_FILE = Path("data/last_run_stats.json")
MIN_OK_RATIO = 0.5


def main() -> int:
    if not STATS_FILE.exists():
        print(f"::warning::找不到 {STATS_FILE}，跳过质量门禁")
        return 0

    try:
        stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"::warning::读取 {STATS_FILE} 失败: {e}")
        return 0

    total = stats.get("total", 0)
    if total == 0:
        print("::warning::本次运行没有发生 Claude 调用")
        return 0

    ok = stats.get("ok", 0)
    ratio = stats.get("ok_ratio", 0.0)
    print(f"Claude 分析成功率: {ok}/{total} ({ratio:.0%})")

    for reason, count in sorted(
        stats.get("reasons", {}).items(), key=lambda kv: -kv[1]
    ):
        print(f"  - {reason}: {count} 次")

    if stats.get("auth_failed"):
        print(
            "::error::Claude CLI 认证失效。请在本机运行 `claude setup-token` "
            "生成长期 token，并更新 GitHub Secret: CLAUDE_CODE_OAUTH_TOKEN"
        )
        return 1

    if ratio < MIN_OK_RATIO:
        print(
            f"::error::Claude 分析成功率 {ratio:.0%} 低于阈值 {MIN_OK_RATIO:.0%}，"
            "本次内容基本由规则评分产生（摘要为正文截断）"
        )
        return 1

    print("质量门禁通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
