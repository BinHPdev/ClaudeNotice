#!/bin/bash
# ============================================================
# ClaudeNotice — macOS 自托管 Runner 安装脚本
# 运行一次即可，之后 Runner 作为后台服务自动启动
#
# 使用前请先：
#   1. 在 GitHub 仓库页面 → Settings → Actions → Runners
#   2. 点击 "New self-hosted runner" → macOS → 复制 token
#   3. 将 token 粘贴到下面的 RUNNER_TOKEN 变量
# ============================================================

set -e

# ── 配置区（修改这里）───────────────────────
GITHUB_REPO="https://github.com/BinHPdev/ClaudeNotice"
RUNNER_TOKEN="YOUR_RUNNER_TOKEN_FROM_GITHUB"
RUNNER_NAME="my-mac-runner"
RUNNER_DIR="$HOME/actions-runner"
# ────────────────────────────────────────────

echo "======================================"
echo "  ClaudeNotice Runner 安装脚本"
echo "======================================"

# 1. 检查依赖
command -v python3 >/dev/null || { echo "❌ 需要安装 Python 3"; exit 1; }
command -v git     >/dev/null || { echo "❌ 需要安装 git"; exit 1; }
command -v claude  >/dev/null || echo "⚠️  未检测到 claude CLI，Claude 处理步骤将降级为规则模式"

# 2. 下载 Runner
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# 获取最新版本号
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/')
RUNNER_PKG="actions-runner-osx-arm64-${RUNNER_VERSION}.tar.gz"

# Apple Silicon Mac 用 arm64，Intel Mac 改为 x64
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
  RUNNER_PKG="actions-runner-osx-x64-${RUNNER_VERSION}.tar.gz"
fi

if [ ! -f "run.sh" ]; then
  echo "📦 下载 GitHub Actions Runner v${RUNNER_VERSION}..."
  curl -sOL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_PKG}"
  tar xzf "$RUNNER_PKG"
  rm "$RUNNER_PKG"
fi

# 3. 配置 Runner
echo "⚙️  配置 Runner..."
./config.sh \
  --url "$GITHUB_REPO" \
  --token "$RUNNER_TOKEN" \
  --name "$RUNNER_NAME" \
  --labels "self-hosted,macos" \
  --work "_work" \
  --unattended \
  --replace

# 4. 安装为 macOS 后台服务（launchd）
echo "🚀 安装为系统服务..."
./svc.sh install
./svc.sh start

echo ""
echo "======================================"
echo "  ✅ Runner 安装完成！"
echo ""
echo "  状态查看: cd $RUNNER_DIR && ./svc.sh status"
echo "  停止服务: cd $RUNNER_DIR && ./svc.sh stop"
echo "  启动服务: cd $RUNNER_DIR && ./svc.sh start"
echo ""
echo "  Runner 会在开机时自动启动。"
echo "  GitHub Actions 触发时会在你的 Mac 上执行任务。"
echo "======================================"
