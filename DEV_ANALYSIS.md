# ClaudeNotice 开发分析文档

> 版本：v0.1-draft | 日期：2026-03-01 | 分支：dev
>
> **目标**：打造最前沿、全面、实用的 Claude & AI 相关消息一键获取平台，针对初级 / 中级 / 高级读者分层投递内容，帮助读者从入门到领域前沿。

---

## 目录

1. [竞品与参考项目分析](#一竞品与参考项目分析)
2. [数据源全景图](#二数据源全景图)
3. [ClaudeNotice 现状评估](#三claudenotice-现状评估)
4. [差距分析（Gap Analysis）](#四差距分析gap-analysis)
5. [优化方向与优先级](#五优化方向与优先级)
6. [分层读者内容策略](#六分层读者内容策略)
7. [开发路线图（草稿）](#七开发路线图草稿)
8. [待共创决策点](#八待共创决策点)

---

## 一、竞品与参考项目分析

### 1.1 Top 参考项目矩阵

| # | 项目 | Stars | 语言 | 数据源类型 | 核心亮点 | 对本项目的启示 |
|---|------|-------|------|-----------|---------|--------------|
| 1 | **RSSHub** | 42k+ | TypeScript | API/爬虫/RSS | 万能 RSS 生成器，1000+ 路由 | 数据源扩展架构：路由模式可复用 |
| 2 | **RSS-Bridge** | 8.7k | PHP | 爬虫/CSS选择器 | 447+ 桥接，无 RSS 网站转换 | 通用爬虫桥接思路 |
| 3 | **Miniflux** | 8.8k | Go | RSS/Atom | 极简单二进制，25+ 集成 | Telegram/Discord 推送集成方案 |
| 4 | **auto-news** | 841 | Python | RSS+Twitter+YouTube+Reddit | LLM 驱动多源聚合 | **最接近本项目的架构参考** |
| 5 | **feeds.fun** | 344 | Python | RSS | AI 自动标签 + 用户评分规则 | 智能标签 + 个性化过滤机制 |
| 6 | **hacker-news-digest** | 744 | Python | HN API | ChatGPT 摘要 + GitHub Pages | 与本项目架构最相似的 MVP |
| 7 | **RSSbrew** | 273 | Python | RSS | RSS 处理中间层 + AI Digest | Digest 生成模式 |
| 8 | **trafilatura** | 5.4k | Python | 爬虫 | 高精度正文提取 | 可替代 newspaper3k 提升内容质量 |
| 9 | **newspaper3k** | 15k | Python | 爬虫 | 成熟的新闻提取库 | 全文抓取的底层库 |
| 10 | **NewsBlur** | 7.3k | Python | RSS | ML 个性化过滤，完整生产架构 | 个性化推荐机制参考 |

### 1.2 关键架构模式对比

```
┌─────────────────────────────────────────────────────────────┐
│                    内容聚合项目架构谱系                        │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  纯 RSS 阅读 │  RSS 生成/桥接│  LLM 增强聚合│  专项领域聚合   │
│  Miniflux    │  RSSHub       │  auto-news   │  HN Digest     │
│  FreshRSS    │  RSS-Bridge   │  feeds.fun   │  ClaudeNotice  │
│  yarr        │  RSSbrew      │              │  ← 我们在这里   │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

**本项目的差异化优势**：垂直领域（Claude/AI）+ LLM 增强 + 分层读者 + 中英双语 + 自动化部署，这个组合在开源生态中几乎空白。

### 1.3 主要竞品优势与不足汇总

**auto-news 的最佳实践（可借鉴）**：
- 多 LLM 后端（OpenAI / Gemini / Ollama）
- 每周 Top 内容 Recap
- LLM 相关性过滤（过滤掉 ~80% 不相关内容）
- YouTube 视频自动转录

**hacker-news-digest 的最佳实践（可借鉴）**：
- 双模型备用（ChatGPT 失败 → 本地 T5）
- GitHub Pages 静态站，零成本
- RSS 输出（用户可订阅）

**feeds.fun 的最佳实践（可借鉴）**：
- AI 标签 + 用户自定义规则 = 真正个性化
- Loader Worker / Librarian Worker 分层架构

---

## 二、数据源全景图

### 2.1 官方渠道

| 数据源 | 获取方式 | 更新频率 | 难度 | 读者层级 | 当前状态 |
|--------|---------|---------|------|---------|---------|
| Anthropic 博客 | HTML 解析（无原生 RSS）| 不定期，周均 1-3 篇 | 中 | 全层级 | ✅ 已实现（但发布时间不准） |
| Anthropic 研究 | HTML 解析 | 月均 1-4 篇 | 中 | 高级 | ✅ 已实现 |
| Claude API Release Notes | HTML 解析 `docs.anthropic.com` | 每 1-2 周 | 易 | 中/高级 | ❌ 缺失 |
| Claude 状态页 | Statuspage Atom Feed | 故障时实时 | 易 | 中级 | ❌ 缺失 |
| Anthropic GitHub Releases | `github.com/anthropics/*/releases.atom` | 随 SDK 发版 | 易 | 高级 | ❌ 缺失 |
| OpenAI 官方博客 | `openai.com/news/rss.xml` | 周均 1-5 篇 | 易 | 全层级 | ❌ 缺失 |
| OpenAI API Changelog | HTML/RSS `developers.openai.com` | 周均 1-3 次 | 易 | 中/高级 | ❌ 缺失 |

### 2.2 SDK / 包更新渠道

| 数据源 | RSS/API | 读者层级 | 当前状态 |
|--------|---------|---------|---------|
| PyPI anthropic 包 | `pypi.org/rss/project/anthropic/releases.xml` | 高级 | ❌ 缺失 |
| PyPI openai 包 | `pypi.org/rss/project/openai/releases.xml` | 高级 | ❌ 缺失 |
| anthropic-sdk-python Releases | `github.com/anthropics/anthropic-sdk-python/releases.atom` | 高级 | ❌ 缺失 |
| claude-code Releases | `github.com/anthropics/claude-code/releases.atom` | 高级 | ❌ 缺失 |
| @anthropic-ai/sdk npm | npmrss.com 或 GitHub Releases | 高级 | ❌ 缺失 |

### 2.3 社区渠道

| 数据源 | 获取方式 | 更新频率 | 难度 | 读者层级 | 当前状态 |
|--------|---------|---------|------|---------|---------|
| r/ClaudeAI | PRAW / `.json` 端点 | 实时，每日大量 | 中 | 中级 | ✅ 已实现 |
| r/LocalLLaMA | PRAW / `.json` | 实时 | 中 | 中/高级 | ✅ 已实现 |
| Hacker News | Algolia API（免费） | 实时 | 易 | 中/高级 | ✅ 已实现 |
| X/Twitter Nitter | HTML 解析（不稳定）| 实时 | 难 | 中/高级 | ✅ 已实现（脆弱） |
| Anthropic Discord | Discord Bot（需 Token）| 实时 | 难 | 中级 | ❌ 缺失 |
| GitHub Discussions | GitHub API | 随时 | 中 | 高级 | ❌ 缺失 |

### 2.4 学术 / 技术深度渠道

| 数据源 | RSS/API | 读者层级 | 当前状态 |
|--------|---------|---------|---------|
| arXiv cs.AI | `rss.arxiv.org/rss/cs.ai` | 高级 | ❌ 缺失 |
| arXiv cs.LG | `rss.arxiv.org/rss/cs.LG` | 高级 | ❌ 缺失 |
| Hugging Face Blog | `huggingface.co/blog/feed.xml` | 高级 | ❌ 缺失 |
| Import AI（Jack Clark）| `importai.substack.com/feed` | 高级 | ❌ 缺失 |
| Latent Space | `www.latent.space/feed` | 高级 | ✅ 已实现 |
| Simon Willison's Weblog | `simonwillison.net/atom/everything/` | 高级 | ✅ 已实现 |
| Interconnects | `www.interconnects.ai/feed` | 高级 | ✅ 已实现 |

### 2.5 AI 专项聚合 / Newsletter

| 数据源 | RSS/地址 | 读者层级 | 当前状态 |
|--------|---------|---------|---------|
| AINews (news.smol.ai) | buttondown RSS | 高级 | ✅ 已实现（AI News Buttondown） |
| Ben's Bites | Beehiiv RSS | 初/中级 | ❌ 缺失 |
| The Batch（deeplearning.ai）| `deeplearning.ai/the-batch/feed/` | 中/高级 | ❌ 缺失 |
| Lilian Weng Blog | `lilianweng.github.io/index.xml` | 高级 | ✅ 已实现 |
| Eugene Yan | `eugeneyan.com/rss.xml` | 高级 | ✅ 已实现 |

### 2.6 中文渠道

| 数据源 | 获取方式 | 读者层级 | 当前状态 |
|--------|---------|---------|---------|
| 少数派 AI | RSS `sspai.com/tag/AI/feed` | 初/中级 | ✅ 已实现 |
| InfoQ AI 频道 | RSS | 中/高级 | ✅ 已实现 |
| V2EX Claude 节点 | HTML 解析 | 中级 | ✅ 已实现 |
| 掘金 Claude 标签 | API | 中级 | ✅ 已实现（有冗余请求） |
| 知乎 Claude 话题 | RSSHub 路由（需 Cookie）| 初级 | ❌ 缺失 |
| 微信公众号 | wewe-rss（自部署）| 初/中级 | ❌ 缺失（获取难） |
| 即刻 AI 话题 | RSSHub 路由 | 初级 | ❌ 缺失 |

### 2.7 新闻媒体

| 数据源 | RSS | 读者层级 | 当前状态 |
|--------|-----|---------|---------|
| TechCrunch Anthropic 标签 | `techcrunch.com/tag/anthropic/feed/` | 初/中级 | ✅ 已实现（TechCrunch AI 频道）|
| The Verge AI | RSS | 初/中级 | ✅ 已实现 |
| Wired AI | RSS | 中级 | ✅ 已实现 |
| VentureBeat AI | RSS | 中级 | ✅ 已实现 |
| Google News RSS（关键词）| 自动生成 URL | 初/中级 | ❌ 缺失（高价值补充）|
| MIT Technology Review | RSS | 高级 | ❌ 缺失 |

### 2.8 数据源覆盖热力图（当前 vs 理想）

```
层级       官方动态  SDK更新  社区热点  深度技术  中文内容  Newsletter
─────────────────────────────────────────────────────────────────────
初级          🟡        ❌       🟡       ❌        🟡        ❌
中级          🟡        ❌       ✅       ❌        🟡        🟡
高级          🟡        ❌       🟡       🟡        ❌        🟡

✅ 覆盖完善  🟡 部分覆盖  ❌ 缺失
```

**最大缺口**：SDK/包版本更新、arXiv 学术论文、初级读者友好内容（Ben's Bites、知乎）、Discord 社区。

---

## 三、ClaudeNotice 现状评估

### 3.1 功能清单（已实现 ✅ / 缺失 ❌ / 部分 🟡）

**数据采集**
- ✅ RSS/Atom 抓取（14 个英文源）
- ✅ YouTube RSS（3 个频道）
- ✅ Anthropic 官网 HTML 解析（但发布时间不准）
- ✅ Hacker News Algolia API
- ✅ GitHub 仓库搜索（Topic + 关键词）
- ✅ Reddit（PRAW + 降级只读）
- 🟡 X/Twitter（Nitter 方案，不稳定）
- ✅ 中文源（少数派 / InfoQ / V2EX / 掘金）
- ❌ PyPI/npm 包版本更新
- ❌ Anthropic GitHub Releases Atom
- ❌ Claude API Release Notes
- ❌ OpenAI 官方博客
- ❌ arXiv 学术论文
- ❌ Discord 消息抓取
- ❌ Google News RSS

**内容处理**
- ✅ 三层去重（raw_id + URL + 标题哈希）
- ✅ 跨天去重（seen_ids.json）
- ✅ 关键词过滤（黑名单 + 白名单）
- ✅ Claude CLI 智能分析（相关性 + 摘要 + 标签 + 评分）
- ✅ 规则评分降级（CLI 不可用时）
- ✅ 前沿/成熟分类（7 天阈值）
- ❌ 并发处理（配置了 claude_concurrency: 3 但未实现）
- ❌ 全文抓取（只有摘要）
- ❌ 读者分层（无初/中/高级分类）
- ❌ 内容质量的综合评判（只有 AI 分数，无多维度）

**输出与分发**
- ✅ 静态 HTML 单页（Tailwind CSS + 暗色模式）
- ✅ 标签筛选（前端 JS）
- ✅ 今日速览导语（Claude CLI）
- ✅ GitHub Pages 自动部署
- ❌ RSS 输出（无法订阅）
- ❌ Telegram / Discord 推送
- ❌ 邮件 Newsletter
- ❌ 分页（全部内容在一页，体积大）
- ❌ 全文搜索

### 3.2 已知技术问题

| 问题 | 严重度 | 位置 |
|------|--------|------|
| Nitter 实例随时全部下线 | 🔴 高 | `twitter.py` |
| Anthropic 官网无法获取真实发布时间 | 🟡 中 | `rss.py:_scrape_anthropic_html` |
| 掘金冗余 GET 请求 | 🟢 低 | `chinese.py:131-136` |
| Claude CLI 串行调用（100条需50秒+）| 🟡 中 | `pipeline.py` |
| GitHub Trending 未实现 | 🟡 中 | `github_scraper.py` |
| JSON 解析正则贪心匹配风险 | 🟢 低 | `claude_cli.py` |
| `click` 依赖未使用 | 🟢 低 | `requirements.txt` |
| 无任何测试 | 🟡 中 | 整体 |
| 无错误告警通知 | 🟡 中 | 整体 |

### 3.3 架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构设计 | 8/10 | 三层分离清晰，配置驱动好 |
| 数据源覆盖 | 5/10 | 缺失 SDK 更新、OpenAI、arXiv 等重要源 |
| 内容质量处理 | 6/10 | 基础 AI 分析有，但无全文、无分层 |
| 可靠性 | 5/10 | 强依赖 Nitter + 本机 Claude CLI |
| 分发渠道 | 4/10 | 仅 GitHub Pages，无订阅渠道 |
| 读者体验 | 6/10 | 单页可用，无分层内容 |
| **综合** | **6/10** | 扎实的 MVP，有很大提升空间 |

---

## 四、差距分析（Gap Analysis）

### 4.1 数据源缺口（Top Priority）

```
当前有 ──────────────────────────────────────► 需要补充
Anthropic Blog (HTML, 时间不准)                Anthropic Blog (真实发布时间)
无                                             claude-code GitHub Releases Atom ⭐
无                                             anthropic-sdk-python Releases Atom ⭐
无                                             PyPI anthropic 版本 RSS ⭐
无                                             OpenAI 官博 RSS ⭐
无                                             Claude API Release Notes ⭐
Reddit (有)                                    r/Anthropic subreddit (缺失)
GitHub 仓库搜索 (有)                           GitHub Discussions + Issues ⭐
Latent Space / Simon Willison (有)             arXiv cs.AI/cs.LG ⭐（高级读者）
Nitter (不稳定)                                稳定的 X 数据源方案
无                                             Ben's Bites / The Batch（初级友好）
少数派 / InfoQ (有)                            知乎 / 即刻 / 微信公众号
```

⭐ = 高价值且容易实现

### 4.2 内容处理缺口

```
当前 ──────────────────────────────────────► 需要补充
7天/成熟 二分类                               初级/中级/高级 三层读者分类
只有摘要，无全文                              全文抓取（trafilatura）+ 摘要
Claude CLI 串行                               并发调用（已配置未实现）
标签: 9个固定                                 动态扩展标签体系
单一来源评分                                  多维度评分（热度+质量+新鲜度+难度）
无阅读时长估计                               阅读时长标注（初级友好）
```

### 4.3 分发渠道缺口

```
当前 ──────────────────────────────────────► 需要补充
GitHub Pages HTML（仅）                       RSS 输出（让用户订阅）⭐
无推送                                        Telegram 频道 ⭐
无订阅                                        邮件 Digest（周报）
无历史                                        历史归档页面 + 搜索
```

---

## 五、优化方向与优先级

### Priority 1：补充核心数据源（高价值低成本）

这些是 RSS Feed，直接在 `config.yml` 中添加 URL 即可，开发成本极低：

```yaml
# 新增到 config.yml 的 rss_feeds 节点
- name: "Claude Code Releases"
  url: "https://github.com/anthropics/claude-code/releases.atom"
  source_type: "official"

- name: "Anthropic SDK Python Releases"
  url: "https://github.com/anthropics/anthropic-sdk-python/releases.atom"
  source_type: "official"

- name: "PyPI anthropic"
  url: "https://pypi.org/rss/project/anthropic/releases.xml"
  source_type: "official"

- name: "OpenAI 官方博客"
  url: "https://openai.com/news/rss.xml"
  source_type: "official"

- name: "Ben's Bites"
  url: "https://bensbites.beehiiv.com/feed"
  source_type: "blog"

- name: "Import AI"
  url: "https://importai.substack.com/feed"
  source_type: "blog"

- name: "The Batch"
  url: "https://www.deeplearning.ai/the-batch/feed/"
  source_type: "blog"

- name: "arXiv cs.AI"
  url: "https://rss.arxiv.org/rss/cs.ai"
  source_type: "research"

- name: "HuggingFace Blog"
  url: "https://huggingface.co/blog/feed.xml"
  source_type: "official"
```

### Priority 2：修复现有问题

- [ ] **修复 Anthropic 官网发布时间**：从文章详情页提取真实时间，或使用社区维护的 RSS（`Olshansk/rss-feeds`）
- [ ] **修复掘金冗余请求**：删除无效 GET，直接 POST
- [ ] **实现 Claude CLI 并发**：`asyncio` + `ThreadPoolExecutor`，利用已配置的 `claude_concurrency: 3`
- [ ] **JSON 解析增强**：用 `re.search(r'\{[^{}]*\}', ...)` 非贪心匹配，防止嵌套 JSON 问题

### Priority 3：读者分层系统

在 `Article` 数据模型新增 `reader_level` 字段，Claude CLI 分析时同步输出：

```python
# 新增 Prompt 指令
"reader_level": "beginner|intermediate|advanced",
# beginner: 使用体验、教程、新功能介绍
# intermediate: 工作流、最佳实践、工具集成
# advanced: 研究论文、架构设计、SDK 变更、底层原理
```

### Priority 4：X/Twitter 替代方案

Nitter 不稳定，备选方案（按优先级）：

1. **Google News RSS 关键词搜索**（立即可用）：
   ```
   https://news.google.com/rss/search?q=Anthropic+Claude&hl=en-US&gl=US&ceid=US:en
   ```
2. **RSS.app / FetchRSS**（付费，稳定）：监控核心 X 账号
3. **保留 Nitter 作为降级**，但不依赖它作为主要来源

### Priority 5：输出渠道扩展

- [ ] **RSS 输出**：生成 `docs/feed.xml`，让用户能在 RSS 阅读器订阅
- [ ] **Telegram 频道推送**：每日精选 Top 5 自动推送
- [ ] **周报 Digest**：每周一汇总上周热点（Claude CLI 生成）

---

## 六、分层读者内容策略

### 6.1 三层读者画像

**初级 (Beginner)**
- 身份：刚接触 Claude / AI 工具的用户，学生、普通职场人
- 需求：What is 类内容、使用教程、工具推荐、中文友好
- 内容类型：官方发布公告（用户向）、使用体验分享、中文媒体报道
- 阅读时长：5 分钟以内
- 数据源侧重：Anthropic 官方新闻（非研究）、Ben's Bites、中文媒体、Reddit r/ClaudeAI 高赞帖

**中级 (Intermediate)**
- 身份：有一定使用经验的开发者/从业者，希望提效
- 需求：最佳实践、工作流技巧、工具集成、新功能深度介绍
- 内容类型：技术博客、GitHub 优质项目、HN 讨论、开发者 Newsletter
- 阅读时长：10-20 分钟
- 数据源侧重：Simon Willison、Latent Space、GitHub Projects、HN、Reddit r/LocalLLaMA

**高级 (Advanced)**
- 身份：AI 工程师、研究者、架构师，希望掌握领域前沿
- 需求：技术原理、研究论文、SDK 变更、模型能力边界探索
- 内容类型：arXiv 论文、Anthropic Research、SDK Release Notes、Import AI
- 阅读时长：30 分钟+
- 数据源侧重：arXiv、Anthropic Research、GitHub Releases、Import AI、Lilian Weng

### 6.2 内容分层标签映射

```python
READER_LEVEL_RULES = {
    "beginner": {
        "source_types": ["official_news", "chinese"],
        "tags": ["新功能介绍", "使用教程", "产品公告"],
        "score_floor": 50,        # 需要有一定热度（社区验证过的内容）
    },
    "intermediate": {
        "source_types": ["blog", "community", "news"],
        "tags": ["工作流", "最佳实践", "工具集成", "提效技巧"],
        "score_floor": 20,
    },
    "advanced": {
        "source_types": ["research", "official_technical", "sdk_release"],
        "tags": ["模型能力", "研究论文", "SDK更新", "架构设计", "提示工程"],
        "score_floor": 0,         # 学术内容热度低但价值高
    },
}
```

### 6.3 网站改版方向

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ ClaudeNotice    [初级] [中级] [高级]    🔍 搜索   🌙   │
├──────────────────────────────────────────────────────────────┤
│  📊 今日摘要                                                  │
│  今日收录 47 条 | 初级 12 | 中级 23 | 高级 12 | 更新 08:00  │
├──────────────────────────────────────────────────────────────┤
│  🔥 今日热点（Claude CLI 生成 3 句导语）                      │
├──────────┬───────────────────────────────────────────────────┤
│  📌 官方  │  Claude Code v1.x.x 发布 | PyPI anthropic 更新   │
│  动态     │  [高优先级卡片]                                   │
├──────────┼───────────────────────────────────────────────────┤
│  🚀 前沿  │  按读者层级显示：初/中/高 Tab 切换               │
│  速递     │  每条标注：[初级] [中级] [高级] 难度标签 阅读时长  │
├──────────┼───────────────────────────────────────────────────┤
│  📚 精华  │  本周 Top 10（编辑精选）                         │
│  沉淀     │                                                   │
└──────────┴───────────────────────────────────────────────────┘
```

---

## 七、开发路线图（草稿）

> ⚠️ 以下为待共创内容，具体节奏和优先级请与用户确认

### Phase 1：数据源补全 + BugFix（建议先做）

**目标**：不改变架构，快速补齐最重要的缺口

- [ ] `config.yml` 新增 8-10 个高价值 RSS 源（GitHub Releases + PyPI + OpenAI + Ben's Bites + arXiv）
- [ ] 修复 Anthropic 官网发布时间（改用 Olshansk 社区 RSS）
- [ ] 修复掘金冗余请求
- [ ] 添加 `source_type: "sdk_release"` 和 `source_type: "research"` 两种新类型
- [ ] 修复 JSON 解析正则问题
- [ ] X/Twitter 降级为次要来源，Google News RSS 作为补充

**预期效果**：数据源从 ~20 个增加到 ~35 个，覆盖 SDK 更新和学术内容。

---

### Phase 2：读者分层系统

- [ ] `Article` 新增 `reader_level: str` 字段
- [ ] Claude CLI Prompt 升级（输出 `reader_level` 字段）
- [ ] 降级规则补充（source_type → reader_level 映射）
- [ ] 网站前端：Tab 切换（初级 / 中级 / 高级 / 全部）
- [ ] 文章卡片新增难度标签和阅读时长估算

---

### Phase 3：处理能力提升

- [ ] 实现 Claude CLI 并发（`ThreadPoolExecutor(max_workers=3)`）
- [ ] 集成 `trafilatura` 实现全文抓取（可选，对高级内容）
- [ ] 多维度评分（热度 + 质量 + 新鲜度 + 难度，加权综合）
- [ ] `data/raw/` 按源分目录存储，便于审计

---

### Phase 4：分发渠道扩展

- [ ] RSS 输出（生成 `docs/feed.xml` + `docs/feed-beginner.xml` 等）
- [ ] Telegram Bot 推送（每日 Top 5 按层级推送）
- [ ] 每周 Digest 页面（`docs/weekly/YYYY-Wxx.html`）

---

### Phase 5：体验优化

- [ ] 分页（每页 20 条，避免单页过大）
- [ ] 全文搜索（Fuse.js 客户端搜索）
- [ ] 来源统计图表（Recharts 或 Chart.js）
- [ ] 错误告警通知（GitHub Actions 失败时 Telegram/邮件通知）

---

## 八、待共创决策点

以下问题需要与你确认，影响具体实现方向：

### D1：OpenAI 内容的定位
> 当前项目名为 ClaudeNotice，是否要包含 OpenAI 相关内容？
> - 方案 A：只聚合 Claude/Anthropic，保持垂直聚焦
> - 方案 B：扩展为"主流 AI 工具导览"，Claude 为主 OpenAI 为辅
> - 方案 C：完全对等，重命名为 AINotice 或类似名称

### D2：X/Twitter 方案
> Nitter 长期不可靠，如何处理 Twitter 数据源？
> - 方案 A：放弃 Twitter，用 Google News RSS + 更多技术博客替代
> - 方案 B：付费使用 RSS.app 订阅核心账号（每月 ~$9）
> - 方案 C：保留 Nitter 降级，不主动依赖它
> - 方案 D：等待 Twitter API 价格下调再接入

### D3：读者分层的呈现方式
> - 方案 A：Tab 切换（初 / 中 / 高 / 全部）—— 界面简洁
> - 方案 B：同一页面每条标注难度徽章 —— 一览无余
> - 方案 C：三个独立页面（分别维护）—— 内容可深度定制

### D4：AI 分析依赖
> 当前强依赖本机 Claude CLI，如果更换机器或断网则分析失效
> - 方案 A：保持现状（MVP 优先，本机运行）
> - 方案 B：增加 Anthropic API 直接调用作为备用（需 API Key）
> - 方案 C：同时支持 Claude CLI + API + 规则降级三层

### D5：内容语言策略
> - 方案 A：英文原文 + Claude 生成中文摘要（现状）
> - 方案 B：为中文读者生成更长的中文解读（500字+）
> - 方案 C：双语摘要（英文原文摘要 + 中文翻译）

### D6：推送渠道优先级
> 有限开发资源下，哪个推送渠道最优先？
> - 方案 A：RSS 输出（零成本，用户自主订阅）
> - 方案 B：Telegram 频道推送（即时触达，操作门槛低）
> - 方案 C：邮件周报（覆盖不用 Telegram 的用户）

---

## 附录：快速可添加的数据源 URL

以下 RSS 源可直接复制到 `config.yml`，无需新增爬虫代码：

```yaml
# === 官方 / SDK 更新 ===
- {name: "Claude Code GitHub Releases", url: "https://github.com/anthropics/claude-code/releases.atom", source_type: "official"}
- {name: "Anthropic SDK Python", url: "https://github.com/anthropics/anthropic-sdk-python/releases.atom", source_type: "official"}
- {name: "Anthropic SDK TypeScript", url: "https://github.com/anthropics/anthropic-sdk-typescript/releases.atom", source_type: "official"}
- {name: "PyPI anthropic", url: "https://pypi.org/rss/project/anthropic/releases.xml", source_type: "official"}
- {name: "PyPI openai", url: "https://pypi.org/rss/project/openai/releases.xml", source_type: "official"}
- {name: "OpenAI 官方博客", url: "https://openai.com/news/rss.xml", source_type: "official"}
- {name: "HuggingFace Blog", url: "https://huggingface.co/blog/feed.xml", source_type: "official"}

# === 学术研究（高级）===
- {name: "arXiv cs.AI", url: "https://rss.arxiv.org/rss/cs.ai", source_type: "research"}
- {name: "arXiv cs.LG", url: "https://rss.arxiv.org/rss/cs.LG", source_type: "research"}
- {name: "Import AI Newsletter", url: "https://importai.substack.com/feed", source_type: "blog"}

# === Newsletter（初/中级）===
- {name: "Ben's Bites", url: "https://bensbites.beehiiv.com/feed", source_type: "blog"}
- {name: "The Batch", url: "https://www.deeplearning.ai/the-batch/feed/", source_type: "blog"}
- {name: "MIT Technology Review AI", url: "https://www.technologyreview.com/topic/artificial-intelligence/feed/", source_type: "news"}

# === 中文（初/中级）===
- {name: "V2EX Claude 节点", url: "https://www.v2ex.com/feed/claude.xml", source_type: "community"}
# 注：V2EX 已通过 HTML 解析实现，改为 RSS 更稳定

# === Google News 关键词（覆盖面广）===
# 动态生成，需在 rss.py 中添加 Google News RSS 构造逻辑
# URL 格式: https://news.google.com/rss/search?q=Anthropic+Claude&hl=en-US&gl=US&ceid=US:en
```

---

*本文档为草稿，待与开发者共创确认后进入实施阶段。*
