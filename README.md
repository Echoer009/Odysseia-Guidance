# Odysseia - 类脑娘社区 AI 助手

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-5865F2?logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)

Odysseia 是一个为 Discord 社区"类脑"量身打造的、功能丰富的 AI 助手。其核心是拥有鲜明人设的 AI "类脑娘"，她不仅能与社区成员进行富有个性的互动，还集成了一系列旨在提升社区活跃度、帮助新人融入的功能。

---

## 目录

- [核心功能](#-核心功能)
- [系统架构](#-系统架构)
- [项目结构](#-项目结构)
- [部署指南](#-部署指南)
- [配置说明](#%EF%B8%8F-配置说明)
- [使用方法与命令列表](#-使用方法与命令列表)
- [开发指南](#-开发指南)
- [常见问题](#-常见问题)
- [许可证](#-许可证)

---

## ✨ 核心功能

### "类脑娘" AI 对话
- **鲜明人设**: 拥有独特的性格、记忆和情感，能以"类脑娘"的身份与用户进行自然、有趣的对话
- **个人记忆**: 能够通过对话学习并记住用户的个人信息（如昵称、偏好），让互动更加个性化
- **多 Provider 支持**: 支持 Google Gemini、OpenAI 兼容 API、DeepSeek 等多个 AI Provider，并支持自动故障转移
- **工具调用**: 能够调用外部工具（获取用户头像、塔罗牌占卜、联网搜索等）来完成特定任务
- **RAG 检索**: 基于世界书、论坛帖子和教程进行检索增强生成，提供更准确的回答

### 动态好感度系统
- **多样互动**: 通过喂食、赠送礼物、聊天等方式，可以提升与"类脑娘"的好感度
- **等级解锁**: 不同的好感度等级会解锁专属的互动和回应
- **每日上限**: 每日聊天获得的好感度有上限，避免刷分

### 社区经济与商店
- **类脑币**: 内置"类脑币"经济系统，用户可通过参与社区活动和游戏赚取货币
- **道具商店**: 用户可以在商店中使用类脑币购买虚拟物品，如用于提升好感度的礼物
- **特殊效果**: 部分道具有特殊效果，如解锁个人记忆、禁用暖贴等

### 内置小游戏
- **二十一点 (Blackjack)**: 与"类脑娘"来一场刺激的牌局，拥有独立 Web UI
- **抽鬼牌 (Ghost Card)**: 经典卡牌游戏，考验你的运气和策略
- **打工 (Work)**: 每日打工赚取类脑币，支持"卖身"自定义内容

### 塔罗牌占卜
- **完整牌组**: 包含大阿卡纳 22 张 + 小阿卡纳 56 张，共 78 张塔罗牌
- **AI 解读**: 抽牌后由类脑娘结合牌意进行个性化解读
- **AI 工具集成**: 作为工具被 AI 调用，在对话中随时可以进行占卜

### 联网搜索
- **SearXNG 集成**: 通过自部署的 SearXNG 搜索引擎进行联网搜索
- **网页抓取**: 支持抓取搜索结果页面内容，提取关键信息
- **AI 工具集成**: 作为工具被 AI 调用，对话中可直接搜索互联网

### 社区世界书 (World Book)
- **社区共建**: 所有社区成员共同构建的知识库，记录社区的文化、历史和梗
- **增量 RAG**: "类脑娘"能够实时查询世界书中的内容，以更准确、更富背景知识地回答
- **混合搜索**: 基于 ParadeDB 的 BM25 全文搜索 + pgvector 向量搜索，双模型 embedding (BGE-M3 + Qwen3)

### 论坛帖子语义搜索
- **向量索引**: 自动将论坛帖子索引到 PostgreSQL 向量数据库
- **语义搜索**: 支持基于语义的帖子搜索，而非简单的关键词匹配
- **历史回溯**: 自动回溯历史帖子，补充索引

### 自动化新成员引导
- **自动化流程**: 当成员获得特定身份组后，引导流程自动触发
- **个性化路径**: 根据用户选择的多个兴趣标签，动态生成独一无二的引导路径
- **Web UI**: 拥有独立的 Vue 3 前端 (`src/guidance/`)，通过 Discord Embedded App SDK 集成

### 暖贴
- **自动评论**: 当频道内有新帖子创建时，"类脑娘"会自动进入并发表评论，帮助启动对话
- **个性化夸奖**: 结合用户记忆生成个性化的夸奖内容
- **用户偏好**: 用户可以选择禁用此功能

### 频道管理
- **频道禁言**: 支持对特定频道进行禁言，禁言后类脑娘不会在该频道响应
- **聊天设置**: 管理聊天功能的全局开关、频道设置、冷却时间等

### 统一管理面板
- **数据库管理**: 交互式浏览和管理数据库内容
- **聊天设置**: 管理聊天功能的全局开关、频道设置、冷却时间等
- **暖贴设置**: 管理启用暖贴功能的论坛频道
- **世界书管理**: 管理社区成员档案和通用知识
- **向量数据库管理**: 管理向量数据库的内容

### 自动化运维
- **定时备份**: 每日自动备份数据库
- **数据库清理**: 自动清理过期数据
- **API 密钥轮换**: 自动轮换和验证 API 密钥
- **Token 用量统计**: 记录和统计 AI 模型的 Token 消耗

---

## 系统架构

### 技术栈

| 类别 | 技术 |
|------|------|
| **语言** | Python 3.13 |
| **Discord 框架** | discord.py 2.0+ |
| **AI 模型** | Google Gemini / DeepSeek / OpenAI 兼容 API |
| **数据库** | PostgreSQL 16 (ParadeDB) — 向量搜索 + 关系数据 |
| **ORM** | SQLAlchemy + Alembic |
| **向量搜索** | pgvector (HNSW) + ParadeDB BM25 |
| **Embedding** | BGE-M3 / Qwen3-Embedding (本地 Ollama) |
| **Web 框架** | FastAPI (后端) + Vue 3 / TypeScript (前端) |
| **反向代理** | Caddy (自动 HTTPS) |
| **搜索引擎** | SearXNG (联网搜索) |

### 服务组件

| 服务 | 说明 |
|------|------|
| `AIService` | AI 对话统一入口，多 Provider 调度和故障转移 |
| `AffectionService` | 好感度系统 |
| `CoinService` | 类脑币经济系统 |
| `ForumSearchService` | 论坛帖子索引和搜索 |
| `IncrementalRAGService` | 增量 RAG 更新 |
| `ThreadCommentorService` | 暖贴功能 |
| `ComfyUIService` | AI 图像生成 |
| `WebSearchService` | SearXNG 联网搜索 |
| `TarotService` | 塔罗牌占卜 |
| `WorkService` | 打工赚钱系统 |
| `KeyRotationService` | API 密钥轮换 |
| `OllamaEmbeddingService` | Ollama 本地 Embedding |
| `OllamaVisionService` | Ollama 本地视觉模型 |
| `ReviewService` | 内容审核服务 |
| `WarningService` | 用户警告服务 |
| `BackupManager` | 定时数据库备份 |
| `TokenUsageService` | AI Token 用量统计 |
| `AIConfigService` | AI Provider/Model 配置管理 |

### Docker 服务 (docker-compose.yml)

| 服务 | 端口 | 说明 |
|------|------|------|
| `bot_app` | — | 主 Discord Bot |
| `db` (ParadeDB) | 5432 | PostgreSQL 数据库 |
| `ollama` | 11434 | 本地 Embedding 模型 (可选, `--profile ollama`) |
| `searxng` | 8080 | SearXNG 联网搜索引擎 |
| `blackjack_web` | 8000 | 二十一点游戏 Web UI |
| `guidance_web` | 8001 | 新人引导 Web UI (Vue 3) |
| `lobby_web` | 8002 | 大厅 Web UI |
| `caddy` | 80/443 | HTTPS 反向代理 |

---

## 项目结构

```
Odysseia-Guidance/
├── src/
│   ├── main.py                    # 主入口，Bot 启动和初始化
│   ├── config.py                  # 全局常量和配置
│   ├── backup/                    # 数据库备份管理
│   ├── chat/                      # 核心聊天系统
│   │   ├── cogs/                  # Discord Cogs (命令和事件处理)
│   │   ├── config/                # 聊天相关配置
│   │   ├── events/                # 节日活动 (圣诞节/万圣节/春节)
│   │   ├── features/              # 功能模块 (每个子目录一个功能)
│   │   │   ├── admin_panel/       # 管理面板
│   │   │   ├── affection/         # 好感度系统
│   │   │   ├── channel_mute/      # 频道禁言
│   │   │   ├── chat_settings/     # 聊天设置
│   │   │   ├── community_member/  # 社区成员
│   │   │   ├── community_posts/   # 社区帖子
│   │   │   ├── events/            # 活动 UI
│   │   │   ├── forum_search/      # 论坛搜索
│   │   │   ├── games/             # 小游戏 (Blackjack + Web UI)
│   │   │   ├── guidance/          # 新人引导
│   │   │   ├── image_generation/  # AI 图像生成 (ComfyUI)
│   │   │   ├── odysseia_coin/     # 类脑币经济系统
│   │   │   ├── personal_memory/   # 个人记忆
│   │   │   ├── tarot/             # 塔罗牌占卜
│   │   │   ├── thread_commentor/  # 暖贴系统
│   │   │   ├── tools/             # AI 工具框架
│   │   │   │   └── functions/     # 具体工具实现
│   │   │   ├── tutorial_search/   # 教程搜索
│   │   │   ├── web_search/        # 联网搜索 (SearXNG)
│   │   │   ├── work_game/         # 打工系统
│   │   │   └── world_book/        # 世界书
│   │   ├── services/              # 服务层
│   │   │   ├── ai/                # AI 服务 (多 Provider)
│   │   │   │   ├── providers/     # Provider 实现 (Gemini/OpenAI/DeepSeek)
│   │   │   │   └── config/        # Provider 和模型配置
│   │   │   ├── embedding_factory.py
│   │   │   ├── key_rotation_service.py
│   │   │   ├── ollama_embedding_service.py
│   │   │   ├── ollama_vision_service.py
│   │   │   ├── prompt_service.py
│   │   │   ├── review_service.py
│   │   │   └── ...
│   │   └── utils/                 # 工具函数
│   ├── database/                  # 数据库层
│   │   ├── database.py            # 数据库连接管理
│   │   ├── models.py              # SQLAlchemy 模型
│   │   └── services/              # 数据库服务
│   ├── guidance/                  # 新人引导 Web 前端 (Vue 3 + Vite)
│   └── lobby/                     # 大厅 Web 前端 (TypeScript + Vite)
├── alembic/                       # 数据库迁移
│   └── versions/                  # 迁移脚本
├── caddy/                         # Caddy 反向代理配置
├── scripts/                       # 维护和管理脚本
├── tests/                         # 测试
├── docker-compose.yml             # Docker 编排
├── requirements.txt               # Python 依赖
├── setup.sh                       # 一键部署脚本
├── alembic.ini                    # Alembic 配置
└── .env.example                   # 环境变量示例
```

---

## 部署指南

本项目提供三种部署方式，请根据需求选择：

| 部署方式 | 适用场景 | 优点 |
|----------|----------|------|
| Docker Compose (本地构建) | 开发调试、自定义修改 | 使用最新代码，方便调试 |
| Docker Compose (公共镜像) | 快速部署、生产环境 | 无需构建，开箱即用 |
| 手动部署 (本地运行) | 本地开发、深度调试 | 灵活控制，便于开发 |

### 前置要求

- Docker 和 Docker Compose (Docker 部署)
- Discord 机器人令牌 ([创建 Bot](https://discord.com/developers/applications))

---

### 方式一：Docker Compose (本地构建) - 推荐

**方式 A：一键配置（推荐）**

```bash
git clone [仓库URL]
cd Odysseia-Guidance
bash setup.sh
```

脚本将引导你完成所有配置，包括 Discord Token、向量模式选择、数据库配置、功能开关等，并自动构建和启动服务。

> **部署完成后**，需要在 Discord 中使用 `/聊天设置` 命令配置 AI Provider 和模型：
> 1. 点击 `🔌 Provider管理` → 添加 AI 端点（Gemini / DeepSeek / OpenAI 兼容等）
> 2. 点击 `🤖 Model管理` → 为 Provider 添加可用模型
> 3. 点击 `更换AI模型` → 选择要使用的模型

**方式 B：手动配置**

```bash
# 1. 克隆项目
git clone [仓库URL]
cd Odysseia-Guidance

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置

# 3. 编辑 docker-compose.yml，取消注释本地构建部分：
#   build:
#     context: .
#     dockerfile: .devcontainer/Dockerfile
# 并注释掉 image: echoni0n/braingirl:latest

# 4. 构建并启动
docker compose build
docker compose up -d

# 5. 初始化数据库
docker compose exec bot_app alembic upgrade head

# 6. (可选) 启动本地向量模式
docker compose --profile ollama up -d
```

---

### 方式二：Docker Compose (公共镜像)

适合快速部署到生产环境，使用预构建的 Docker Hub 镜像。

```bash
# 1. 克隆项目
git clone [仓库URL]
cd Odysseia-Guidance

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置

# 3. 启动服务 (docker-compose.yml 默认使用公共镜像)
docker compose up -d

# 4. 初始化数据库
docker compose exec bot_app alembic upgrade head
```

---

### 方式三：手动部署 (本地运行)

适合本地开发调试。

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 启动 PostgreSQL 数据库
docker run -d \
  --name odysseia_pg \
  -e POSTGRES_DB=${POSTGRES_DB:-odysseia_db} \
  -e POSTGRES_USER=${POSTGRES_USER:-user} \
  -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-password} \
  -p ${DB_PORT:-5432}:5432 \
  -v $(pwd)/pgdata:/var/lib/postgresql/data \
  paradedb/paradedb:latest-pg16

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置

# 4. 运行数据库迁移
alembic upgrade head

# 5. 启动机器人
python -m src.main
```

### 常用 Docker 命令

```bash
docker compose logs -f bot_app          # 查看日志
docker compose down                      # 停止服务
docker compose restart bot_app           # 重启 Bot
docker compose build && docker compose up -d  # 代码更新后重新构建
docker compose --profile ollama up -d    # 启动本地向量模式
```

---

## ⚙️ 配置说明

所有配置通过 `.env` 文件管理。复制 `.env.example` 并填入实际值。

### 必需配置

| 变量 | 说明 |
|------|------|
| `DISCORD_TOKEN` | Discord 机器人令牌（必需） |

> AI Provider 和模型配置在部署后通过 Discord 中的 `/聊天设置` 命令完成，无需在 `.env` 中配置。

### Discord 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GUILD_ID` | 开发服务器 ID，支持逗号分隔多个 | — |
| `DEVELOPER_USER_IDS` | 开发者用户 ID（逗号分隔） | — |
| `ADMIN_ROLE_IDS` | 管理员身份组 ID（逗号分隔） | — |

### 向量模式配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VECTOR_MODE` | 向量模式: `none` / `api` / `local` | `none` |
| `OLLAMA_MODEL` | Ollama Embedding 模型名称 | `qwen3-embedding:0.6b` |
| `OLLAMA_VISION_MODEL` | Ollama 视觉模型名称 | `qwen3.5:0.8b` |

- `none`: 不使用 RAG 检索，直接对话（默认）
- `api`: 使用 Gemini Embedding API (需要 `GOOGLE_API_KEYS_LIST`)
- `local`: 使用 Ollama 本地模型 (需要 `--profile ollama` 启动)

### 数据库配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `POSTGRES_DB` | 数据库名称 | `odysseia_db` |
| `POSTGRES_USER` | 数据库用户名 | `user` |
| `POSTGRES_PASSWORD` | 数据库密码 | `password` |
| `DB_PORT` | 数据库端口 | `5432` |

### 联网搜索配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SEARXNG_URL` | SearXNG 地址 | `http://searxng:8080` |
| `WEB_SEARCH_MAX_RESULTS` | 搜索结果最大返回数 | `5` |
| `WEB_SEARCH_TIMEOUT` | 搜索请求超时 (秒) | `10` |
| `WEB_SCRAPE_TIMEOUT` | 网页抓取超时 (秒) | `15` |
| `WEB_SCRAPE_MAX_LENGTH` | 网页抓取最大字符数 | `5000` |

### 功能开关

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CHAT_ENABLED` | 全局聊天功能开关 | `True` |
| `LOG_AI_FULL_CONTEXT` | 记录 AI 完整上下文 (调试用) | `false` |
| `LOG_DETAILED_GEMINI_PROCESS` | 记录详细 Gemini 处理过程 | `True` |
| `DISABLED_TOOLS` | 禁用的工具模块列表 (逗号分隔) | `get_yearly_summary` |

### 其他配置

| 变量 | 说明 |
|------|------|
| `FORUM_SEARCH_CHANNEL_IDS` | 论坛搜索频道 ID (逗号分隔) |
| `COIN_REWARD_GUILD_IDS` | 类脑币奖励服务器 ID (逗号分隔) |
| `COMFYUI_SERVER_ADDRESS` | ComfyUI 服务器地址 (图像生成) |
| `COMFYUI_WORKFLOW_PATH` | ComfyUI 工作流路径 |
| `PROXY_URL` | 网络代理 URL |

---

## 使用方法与命令列表

### 核心交互
- **自由聊天**: 在任何频道中 `@类脑娘` 或直接回复她的消息，即可开始对话
- **使用命令**: 通过 Discord 的斜杠命令 (`/`) 来使用各项功能

### 主要命令

#### 聊天相关
| 命令 | 说明 |
|------|------|
| `/好感度` | 查询你与类脑娘的好感度状态 |
| `/投喂` | 给类脑娘分享美食，提升好感度 |
| `/忏悔` | 向类脑娘忏悔，可能影响关系 |

#### 经济系统
| 命令 | 说明 |
|------|------|
| `/类脑商店` | 打开商店，购买礼物和道具，查看余额 |

#### 游戏
| 命令 | 说明 |
|------|------|
| `/blackjack` | 开始一局 21 点游戏 |

#### 管理与配置
| 命令 | 说明 |
|------|------|
| `/聊天设置` | 打开聊天功能设置面板 |
| `/数据库管理` | (管理员) 交互式浏览和管理数据库 |
| `/新人引导管理面板` | 打开多功能新人引导管理面板 |

#### AI 工具 (对话中自动调用)
| 工具 | 说明 |
|------|------|
| `get_user_profile` | 获取用户 Discord 个人信息 |
| `tarot_reading` | 进行塔罗牌占卜 |
| `web_search` | 联网搜索 |
| `search` | 搜索世界书和教程 |
| `summarize_channel` | 总结频道消息 |
| `issue_user_warning` | 向用户发出警告 |
| `get_yearly_summary` | 获取年度总结 |

### 新成员引导配置流程

1. **基础配置**: `/新人引导管理面板` → "身份组配置" 和 "消息模板"
2. **创建标签**: 管理面板 → "标签管理"，创建兴趣领域
3. **设置路径**: 管理面板 → "路径设置"，为标签指定频道路径
4. **配置频道消息**: 管理面板 → "频道消息设置"，定义每个频道的介绍内容
5. **部署引导面板**: 管理面板 → "一键部署"
6. **完成**: 成员获得触发身份组时，流程自动开始

---

## 开发指南

### 本地开发环境搭建

```bash
# 1. 克隆项目
git clone [仓库URL]
cd Odysseia-Guidance

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动 PostgreSQL (Docker)
docker run -d --name odysseia_pg \
  -e POSTGRES_DB=odysseia_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  paradedb/paradedb:latest-pg16

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env

# 6. 数据库迁移
alembic upgrade head

# 7. 启动
python -m src.main
```

### 运行测试

```bash
pytest
```

### 数据库迁移

```bash
# 创建新的迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 添加新的 AI 工具

在 `src/chat/features/tools/functions/` 目录下创建新的 Python 文件，定义异步函数并使用 `@register_tool` 装饰器。工具会被 `tool_loader` 自动发现和加载。

### 添加新的 AI Provider

在 `src/chat/services/ai/providers/` 目录下创建新的 Provider 类，继承 `BaseProvider` 并实现 `generate` 方法。然后在配置中注册。

### Web 前端开发

```bash
# 新人引导前端 (Vue 3)
cd src/guidance
npm install
npm run dev

# 大厅前端
cd src/lobby
npm install
npm run dev
```

### 维护脚本

`scripts/` 目录下包含各种维护脚本：

| 脚本 | 说明 |
|------|------|
| `manage_api_keys.py` | 管理 API 密钥 |
| `manage_channel_config.py` | 管理频道配置 |
| `manage_guidance_config.py` | 管理引导配置 |
| `migrate_economy_user_to_pg.py` | 迁移经济数据到 PostgreSQL |
| `migrate_forum_chromadb_to_paradedb.py` | 迁移论坛数据到 ParadeDB |
| `re_embed_forum_with_ollama.py` | 使用 Ollama 重新 embedding |
| `validate_guidance_flow.py` | 验证引导流程 |
| `check_all_dbs.py` | 检查所有数据库状态 |
| `cleanup_duplicate_profiles.py` | 清理重复的用户档案 |

---

## 数据持久化

### Docker 部署
- `./data/` — SQLite 数据库和日志文件
- `./pgdata/` — PostgreSQL 数据持久化目录
- `./ollama_data/` — Ollama 模型数据

### 手动部署
- `pgdata/` — PostgreSQL 数据目录

---

## 常见问题

### Q: 如何启用/禁用聊天功能？
A: 两种方式：
1. 修改 `.env` 中的 `CHAT_ENABLED` 配置（全局紧急开关）
2. 使用 `/聊天设置` 命令在管理面板中配置（更灵活，支持全局/频道/分类级别）

### Q: 如何选择向量模式？
A: 运行 `bash setup.sh` 会引导你选择，或手动设置 `.env` 中的 `VECTOR_MODE`：
- `none`（默认）: 不使用 RAG 检索，直接对话
- `api`: 使用 Gemini Embedding API，需要 API 密钥
- `local`: 使用 Ollama 本地模型，隐私安全，需 `--profile ollama`

### Q: 暖贴功能如何配置？
A: 使用 `/聊天设置` 命令，点击"设置暖贴频道"按钮，选择要启用暖贴功能的论坛频道。

### Q: 如何配置 AI Provider 和模型？
A: 部署完成后，在 Discord 中使用 `/聊天设置` 命令：
1. 点击 `🔌 Provider管理` → 添加 AI 端点（支持 Gemini / DeepSeek / OpenAI 兼容等）
2. 点击 `🤖 Model管理` → 为 Provider 添加可用模型
3. 点击 `更换AI模型` → 选择要使用的模型

系统支持多 Provider 故障转移，会自动切换可用的 Provider。

### Q: 如何查看日志？
A:
- Docker 部署: `docker compose logs -f bot_app`
- 手动部署: 查看 `data/bot_debug.log` 文件

---

## 许可证

本项目采用 [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) 许可证。

AGPL-3.0 是一个 copyleft 许可证，要求如果软件在网络服务器上运行并提供服务，则必须向用户公开源代码。

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 [Issue](../../issues)
- echoer009@gmail.com

---

**Odysseia - 让社区更有温度**
