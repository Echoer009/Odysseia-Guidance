# 通用化改造计划

> 目标: 将项目从"类脑娘专用 Bot"转变为通用 Discord Bot 框架，类脑娘成为其中一个实例配置
> 基于文档: `docs/generalization-audit-report.md`

---

## 核心思路

项目的代码架构本身已是通用的（模块化 Cog、工具自动发现、多 AI Provider、分层记忆注入），问题集中在**内容层**。改造策略：**把内容从代码中抽离到配置文件**。

---

## P0 — 框架核心（必须先做）

### P0-1: Bot 身份配置中心

新建 `config/bot.yaml`，定义所有身份相关常量，一次改全局生效。

```yaml
identity:
  bot_name: "类脑娘"
  community_name: "类脑"
  currency_name: "类脑币"
  mascot_title: "看板娘"
  nickname: "宝宝"
  community_type: "nsfw的airp社区"
```

在 `src/config.py` 中加载并提供全局常量（`config.BOT_NAME`, `config.CURRENCY_NAME` 等）。

**影响范围**: ~700+ 处硬编码引用

**涉及文件**: `src/config.py` + 所有引用硬编码身份字符串的文件

### P0-2: 提示词外部化

将 `src/chat/config/prompts.py` 中硬编码的完整人设提示词抽取到 `config/prompts/` 目录下的 YAML 文件，使用 `{bot_name}` 等占位符。

```yaml
# config/prompts/default.yaml
name: "{bot_name}"
age: 19
community: "{community_name}是一个{community_type}"
persona: "一个热心、真诚、实事求是的社区{mascot_title}..."
```

**涉及文件**（~10 个核心）:
- `src/chat/config/prompts.py` → 改为模板加载器
- `src/chat/services/ai/config/models_config.json` → 移除内嵌人设
- `src/chat/config/chat_config.py` → 提示词片段移到外部
- `src/chat/services/prompt_service.py` → 模板渲染逻辑

### P0-3: 变量/命名去身份化

| 当前 | 改为 | 文件 |
|------|------|------|
| `BRAIN_GIRL_APP_ID` | `BOT_APP_ID` | `src/config.py`, `.env.example` |
| `BRAIN_GIRL_EATING_IMAGES` | `BOT_EATING_IMAGES` | `shop_config.py`, `shop_service.py` |
| `GuidanceBot` 类名 | `DiscordBot` | `src/main.py` |
| `odysseia_coin/` 目录 | `coin/` | 整个目录 + 40+ import |
| `echoni0n/braingirl:latest` | `${DOCKER_IMAGE}` | `docker-compose.yml`, `setup.sh` |
| `braingirl_db` 默认值 | `bot_db` | 6+ 个文件 |

### P0-4: 全局替换硬编码字符串

所有代码中的硬编码身份字符串替换为配置常量引用:

- "类脑娘" (~244 处) → `config.BOT_NAME`
- "类脑币" (~195 处) → `config.CURRENCY_NAME`
- "看板娘" (~73 处) → `config.MASCOT_TITLE`
- "AIRP" / "airp" (~33 处) → `config.COMMUNITY_TYPE`
- "宝宝" 爱称 → `config.NICKNAME`
- "类脑" 社区名 → `config.COMMUNITY_NAME`

**涉及文件**: ~50+ 个 Python/TypeScript/Vue 文件

---

## P1 — 完善通用性

### P1-1: 用户可见文案配置化 (`config/messages.yaml`)

将散布在 ~20 个 cog/service 中的中文文案统一抽取:

```yaml
warnings:
  temp_ban: "你已被 **{bot_name}** 警告并临时封禁"
  footer: "{community_name} · 警告系统"
shop:
  loan_prompt: "你可以从{bot_name}这里借款"
  insufficient: "需要 {price} {currency_name}"
```

### P1-2: 活动/事件模板参数化

`src/chat/events/` 下 ~15 个 XML/MD/JSON 文件中的"类脑娘"改为占位符，活动加载时动态替换。

### P1-3: 越狱提示词策略配置化

当前 `JAILBREAK_*` 三段式注入改为可配置的"内容策略层"，默认不注入，由管理面板控制。

---

## P2 — 数据/内容层

### P2-1: 知识库/世界之书

`world_book/data/knowledge.yml` 标注为示例数据，部署时替换。

### P2-2: 前端文案配置化

guidance/blackjack-web/lobby 前端文案通过 API 从后端配置获取。

### P2-3: Tutorial 目录

作为示例数据保留，文档说明需替换。

---

## 推荐目录结构

```
config/
├── bot.yaml              # Bot 身份核心配置
├── messages.yaml         # 用户可见文案
└── prompts/              # 提示词模板
    ├── default.yaml
    ├── frank.yaml
    ├── gentle.yaml
    ├── feeding.yaml
    ├── confession.yaml
    ├── gift.yaml
    ├── memory_summary.yaml
    └── warmup.yaml
```

---

## 工作量估算

| 优先级 | 改造项 | 文件数 | 复杂度 |
|--------|--------|--------|--------|
| P0 | 身份配置中心 + 全局常量替换 | ~50+ | 高 |
| P0 | 提示词外部化 | ~10 | 高 |
| P0 | 变量/目录重命名 | ~45+ | 中 |
| P1 | 文案配置化 | ~20 | 中 |
| P1 | 活动模板参数化 | ~15 | 中 |
| P2 | 前端/知识库/教程 | ~25 | 低-中 |
