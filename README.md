# ⚡ ClaudeNotice

> Claude Code 最新资讯与最佳实践自动聚合，每日更新

**访问地址**: `https://binhpdev.github.io/ClaudeNotice/`

---

## 功能

- 🚀 **前沿速递** — 7天内最新动态（X、GitHub、HN、Reddit）
- 📚 **成熟实践** — 经验证的最佳使用方法
- 🤖 **Claude CLI 驱动** — 自动中文摘要、质量评分、标签分类
- 🔄 **每日自动更新** — GitHub Actions + 本机自托管 Runner

## 数据来源

| 平台 | 内容 |
|------|------|
| X (Twitter) | @AnthropicAI、@karpathy、@simonw 等影响力账号 |
| GitHub | claude-code 相关仓库和讨论 |
| Hacker News | Claude 相关高赞讨论 |
| Reddit | r/ClaudeAI、r/LocalLLaMA |
| Anthropic Blog | 官方博客和研究更新 |
| 技术媒体 | TechCrunch、VentureBeat、The Verge |
| 优质博客 | Simon Willison、Latent Space、Interconnects |
| 中文源 | 少数派、V2EX、掘金、InfoQ |
| YouTube | Anthropic、Fireship、AI Explained |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 配置

编辑 `config.yml`，按需修改：
- 修改 `site.base_url` 为你的 GitHub Pages 地址
- 配置 Reddit API（可选）

### 3. 本地运行

```bash
# 全量运行：爬取 + 处理 + 生成网站
python main.py

# 单步运行
python main.py scrape    # 只爬取
python main.py process   # 只处理（用 Claude CLI）
python main.py generate  # 只生成网站

# 本地预览
python main.py serve
```

### 4. 部署到 GitHub Pages（自动化）

**步骤 1：创建 GitHub 仓库**
```bash
git init
git remote add origin https://github.com/YOUR_USERNAME/ClaudeNotice.git
git push -u origin main
```

**步骤 2：开启 GitHub Pages**
- 仓库 Settings → Pages → Source 选 `gh-pages` 分支

**步骤 3：安装自托管 Runner（让任务在你的 Mac 上执行）**
- 仓库 Settings → Actions → Runners → New self-hosted runner
- 复制 Token，填入 `scripts/setup_runner.sh`
```bash
# 编辑脚本填入 token 后运行
bash scripts/setup_runner.sh
```

**步骤 4：配置 Secrets（可选）**
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — 提升 Reddit 配额

之后每天北京时间 8:00 自动运行，网站自动更新 ✅

---

## 目录结构

```
ClaudeNotice/
├── scrapers/          各平台爬虫
├── processor/         Claude CLI 内容处理
├── generator/         静态网站生成器
│   └── templates/     HTML 模板
├── data/
│   ├── raw/           原始抓取数据（不提交）
│   └── processed/     处理后数据（提交）
├── site/              生成的静态网站（GitHub Pages）
├── scripts/           工具脚本
│   └── setup_runner.sh  Runner 安装脚本
├── .github/workflows/ GitHub Actions
├── config.yml         数据源配置
└── main.py            主入口
```

## 手动更新

```bash
python main.py  # 运行后 git push 即可
```
