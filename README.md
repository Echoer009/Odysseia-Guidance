# Odysseia - 类脑娘社区AI助手

Odysseia 是一个为 Discord 社区"类脑"量身打造的、功能丰富的AI助手。其核心是拥有鲜明人设的AI"类脑娘"，她不仅能与社区成员进行富有个性的互动，还集成了一系列旨在提升社区活跃度、帮助新人融入的功能。

---

## ✨ 核心功能

### "类脑娘"
- **鲜明人设**: 拥有独特的性格、记忆和情感，能以"类脑娘"的身份与用户进行自然、有趣的对话
- **个人记忆**: 能够通过对话学习并记住用户的个人信息（如昵称、偏好），让互动更加个性化
- **工具调用**: 能够调用外部工具（如获取用户头像、查询教程等）来完成特定任务
- **RAG检索**: 基于世界书和论坛帖子进行检索增强生成，提供更准确的回答

### 动态好感度系统
- **多样互动**: 通过喂食、赠送礼物、聊天等方式，可以提升与"类脑娘"的好感度
- **等级解锁**: 不同的好感度等级会解锁专属的互动和回应
- **每日上限**: 每日聊天获得的好感度有上限，避免刷分

### 社区经济与商店
- **类脑币**: 内置"类脑币"经济系统，用户可通过参与社区活动和游戏赚取货币
- **道具商店**: 用户可以在商店中使用类脑币购买虚拟物品，如用于提升好感度的礼物
- **特殊效果**: 部分道具有特殊效果，如解锁个人记忆、禁用暖贴等

### 内置小游戏
- **二十一点 (Blackjack)**: 与"类脑娘"来一场刺激的牌局
- **抽鬼牌 (Ghost Card)**: 经典卡牌游戏，考验你的运气和策略

### 社区世界书 (World Book)
- **社区共建**: 这是一个由所有社区成员共同构建的知识库，记录着社区的文化、历史和梗
- **增量RAG**: "类脑娘"能够实时查询"世界书"中的内容，以更准确、更富背景知识地回答用户的问题
- **向量搜索**: 基于 ParadeDB 的 BM25 和向量搜索能力，提供高效的语义搜索

### 自动化新成员引导
- **自动化流程**: 当成员获得特定身份组后，引导流程自动触发
- **个性化路径**: 根据用户选择的多个兴趣标签，动态生成独一无二的引导路径
- **分步式引导**: 在每个引导频道中，用户通过点击按钮来获取详细介绍并前往下一站，确保了流程的连贯性

### 暖贴
- **自动评论**: 当频道内有新帖子创建时，"类脑娘"会自动进入并发表评论，帮助启动对话、预热话题
- **个性化夸奖**: 结合用户记忆生成个性化的夸奖内容
- **用户偏好**: 用户可以选择禁用此功能

### 论坛帖子语义搜索
- **向量索引**: 自动将论坛帖子索引到向量数据库
- **语义搜索**: 支持基于语义的帖子搜索，而非简单的关键词匹配
- **历史回溯**: 每天自动回溯历史帖子，补充索引

### 统一管理面板
- **数据库管理**: 交互式浏览和管理数据库内容
- **聊天设置**: 管理聊天功能的全局开关、频道设置、冷却时间等
- **暖贴设置**: 管理启用暖贴功能的论坛频道
- **世界书管理**: 管理社区成员档案和通用知识
- **向量数据库管理**: 管理向量数据库的内容

---

## 系统架构

### 技术栈
- **语言**: Python 3.10+
- **Discord框架**: discord.py 2.0+
- **AI模型**: Google Gemini 2.5/3 Flash/Pro
- **向量数据库**: PostgreSQL (基于 PostgreSQL 16)
- **关系数据库**: SQLite (聊天数据), PostgreSQL (世数据),目前向PostgreSQL迁移中
- **ORM**: SQLAlchemy + Alembic
- **Web框架**: FastAPI (可选的Web UI)

### 数据库说明
- **SQLite (chat.db)**: 用于聊天相关的数据存储（用户档案、好感度、类脑币等）
- **PostgreSQL**: 用于世界书数据（社区成员档案、通用知识等）,用于向量搜索和社区知识库（world_book.sqlite3）

### 服务组件
- **GeminiService**: 处理所有AI对话相关逻辑
- **AffectionService**: 处理好感度系统
- **CoinService**: 处理类脑币经济系统
- **ForumSearchService**: 处理论坛帖子索引和搜索
- **IncrementalRAGService**: 处理增量RAG更新
- **ThreadCommentorService**: 处理暖贴功能
- **ComfyUIService**: 处理AI图像生成

---

## 部署指南

本项目提供三种部署方式，请根据需求选择：

| 部署方式                  | 适用场景             | 优点                   |
| ------------------------- | -------------------- | ---------------------- |
| Docker Compose (本地构建) | 开发调试、自定义修改 | 使用最新代码，方便调试 |
| Docker Compose (公共镜像) | 快速部署、生产环境   | 无需构建，开箱即用     |
| 手动部署 (本地运行)       | 本地开发、深度调试   | 灵活控制，便于开发     |

---

### 方式一：Docker Compose (本地构建) - 推荐

适合开发者，使用本地源代码构建镜像，确保使用最新代码。

#### 前置要求
- Docker 和 Docker Compose
- Discord 机器人令牌
- Google Gemini API 密钥（或自定义端点）

#### 部署步骤

**方式 A：一键配置（推荐）**

```bash
# 克隆项目
git clone [仓库URL]
cd Odysseia-Guidance

# 运行一键配置脚本
bash setup.sh
```

脚本将引导你完成所有配置，包括：
- Discord 机器人令牌
- Google Gemini API 密钥
- 数据库配置
- 功能开关
- 自动构建和启动服务

**方式 B：手动配置**

**1. 克隆项目**
```bash
git clone [仓库URL]
cd Odysseia-Guidance
```

**2. 配置环境变量**
```bash
cp .env.example .env
nano .env
```

**必需配置项**:
```env
# Discord 机器人令牌（必需）
DISCORD_TOKEN="YOUR_DISCORD_TOKEN_HERE"

# Google Gemini API 密钥（必需，至少一个）
GOOGLE_API_KEYS_LIST="
YOUR_GEMINI_API_KEY_1
YOUR_GEMINI_API_KEY_2
"
```

**可选配置项**:
```env
# 开发服务器ID（用于快速同步命令）
GUILD_ID="YOUR_DEVELOPMENT_GUILD_ID_HERE"

# 权限控制
DEVELOPER_USER_IDS="YOUR_USER_ID_1,YOUR_USER_ID_2"
ADMIN_ROLE_IDS="YOUR_ROLE_ID_1,YOUR_ROLE_ID_2"

# PostgreSQL 数据库配置
POSTGRES_DB=braingirl_db
POSTGRES_USER=user
POSTGRES_PASSWORD=password
DB_PORT=5432

# 功能开关
CHAT_ENABLED=True
LOG_AI_FULL_CONTEXT=true

# 工具禁用列表
DISABLED_TOOLS="get_yearly_summary"

# 论坛搜索频道ID
FORUM_SEARCH_CHANNEL_IDS="YOUR_FORUM_CHANNEL_ID_1,YOUR_FORUM_CHANNEL_ID_2"
```

**3. 构建并启动**
```bash
# 构建镜像
docker compose build

# 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps
```

**4. 初始化数据库**
```bash
docker compose exec bot_app alembic upgrade head
```

**5. 查看日志**
```bash
docker compose logs -f bot_app
```

**常用命令**:
```bash
# 停止服务
docker compose down

# 重启服务
docker compose restart bot_app

# 重新构建并启动（代码更新后）
docker compose build && docker compose up -d

# 查看服务状态
docker compose ps
```

---

### 方式二：Docker Compose (公共镜像)

适合快速部署到生产环境，使用预构建的 Docker Hub 镜像。

#### 前置要求
- Docker 和 Docker Compose
- Discord 机器人令牌
- Google Gemini API 密钥（或自定义端点）

#### 部署步骤

**1-2 步** 同方式一

**3. 修改 docker-compose.yml**
编辑 [`docker-compose.yml`](docker-compose.yml:13) 文件，注释掉本地构建，取消注释公共镜像：
```yaml
# 注释掉本地构建
# build:
#   context: .
#   dockerfile: .devcontainer/Dockerfile

# 取消注释公共镜像
image: echoni0n/braingirl:latest
```

**4. 启动服务**
```bash
# 启动所有服务（使用公共镜像）
docker compose up -d

# 查看服务状态
docker compose ps
```

**5-6 步** 同方式一的步骤4-5

---

### 方式三：手动部署 (本地运行)

适合本地开发调试，需要手动管理依赖和服务。

#### 前置要求
- Python 3.10+
- PostgreSQL 16 (用于 ParadeDB)
- pip

#### 部署步骤

**1. 安装 Python 依赖**
```bash
pip install -r requirements.txt
```

**2. 启动 PostgreSQL 数据库**
```bash
# 使用 Docker 快速启动 ParadeDB
docker run -d \
  --name odysseia_pg \
  -e POSTGRES_DB=${POSTGRES_DB:-odysseia_db} \
  -e POSTGRES_USER=${POSTGRES_USER:-user} \
  -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-password} \
  -p ${DB_PORT:-5432}:5432 \
  -v $(pwd)/pgdata:/var/lib/postgresql/data \
  paradedb/paradedb:latest-pg16
```

**3. 配置环境变量**
```bash
cp .env.example .env
nano .env
```

**必需配置项**:
```env
# Discord 机器人令牌（必需）
DISCORD_TOKEN="YOUR_DISCORD_TOKEN_HERE"

# Google Gemini API 密钥（必需，至少一个）
GOOGLE_API_KEYS_LIST="
YOUR_GEMINI_API_KEY_1
YOUR_GEMINI_API_KEY_2
"
```

**可选配置项**:
```env
# 开发服务器ID（用于快速同步命令）
GUILD_ID="YOUR_DEVELOPMENT_GUILD_ID_HERE"

# 权限控制
DEVELOPER_USER_IDS="YOUR_USER_ID_1,YOUR_USER_ID_2"
ADMIN_ROLE_IDS="YOUR_ROLE_ID_1,YOUR_ROLE_ID_2"

# PostgreSQL 数据库配置
POSTGRES_DB=odysseia_db
POSTGRES_USER=user
POSTGRES_PASSWORD=password
DB_PORT=5432

# 功能开关
CHAT_ENABLED=True
LOG_AI_FULL_CONTEXT=true

# 工具禁用列表
DISABLED_TOOLS="get_yearly_summary"

# 论坛搜索频道ID
FORUM_SEARCH_CHANNEL_IDS="YOUR_FORUM_CHANNEL_ID_1,YOUR_FORUM_CHANNEL_ID_2"
```

**4. 运行数据库迁移**
```bash
alembic upgrade head
```

**5. 启动机器人**
```bash
python -m src.main
```

**停止 PostgreSQL**:
```bash
docker stop odysseia_pg
docker rm odysseia_pg
```

---

## 数据持久化说明

### Docker 部署
- `./data/` - SQLite 数据库和日志文件
- `./pgdata/` - PostgreSQL 数据持久化目录

### 手动部署
- `data/chat.db` - SQLite 聊天数据库
- `data/world_book.sqlite3` - 世界书数据库
- `pgdata/` - PostgreSQL 数据目录

**详细的部署测试指南请参考 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)**

---

## 使用方法与命令列表

### 核心交互
- **自由聊天**: 在任何频道中 `@类脑娘` 或直接回复她的消息，即可开始对话
- **使用命令**: 通过 Discord 的斜杠命令 (`/`) 来使用各项功能

### 主要命令

#### 💬 聊天相关
- **`/好感度`**: 查询你与类脑娘的好感度状态
- **`/投喂`**: 给类脑娘分享你的美食，可以提升好感度
- **`/忏悔`**: 向类脑娘忏悔，可能会影响你们的关系

#### 💰 经济系统
- **`/类脑商店`**: 打开商店，使用类脑币购买礼物和道具, 查看余额

#### 🎮 游戏
- **`/blackjack`**: 开始一局刺激的21点游戏（需要配置 VITE_DISCORD_CLIENT_ID）

#### 🛠️ 管理与配置
- **`/聊天设置`**: 打开聊天功能设置面板
- **`/数据库管理`**: (管理员) 以交互方式浏览和管理数据库内容
- **`/新人引导管理面板`**: 打开集成的多功能新人引导管理面板

### 新成员引导配置流程
1. **基础配置**: 运行 `/新人引导管理面板`，进入"身份组配置"和"消息模板"完成基础设置
2. **创建标签**: 在管理面板中，进入"标签管理"，创建你希望新成员选择的兴趣领域
3. **设置路径**: 进入"路径设置"，为上一步创建的每个标签指定一条或多条频道路径
4. **配置频道消息**: 进入"频道消息设置"，为每一个被你设置到路径中的频道定义该频道的介绍内容
5. **部署引导面板**: 进入"一键部署"，将引导面板部署到你希望新成员看到的起始频道
6. **完成**: 现在，当有成员获得你所设置的触发身份组时，整个流程就会自动开始！

---

## ⚙️ 配置说明

### 功能开关

#### CHAT_ENABLED
- **类型**: 布尔值 (True/False)
- **说明**: 全局聊天功能紧急开关，可在不修改数据库的情况下快速禁用整个聊天功能
- **默认值**: True

#### LOG_AI_FULL_CONTEXT
- **类型**: 布尔值 (true/false)
- **说明**: 是否记录AI完整的上下文日志，用于调试
- **默认值**: false

#### DISABLED_TOOLS
- **类型**: 逗号分隔的字符串
- **说明**: 禁用的工具模块列表（文件名，不含.py扩展名）
- **默认值**: "get_yearly_summary"

### 数据库配置

#### PostgreSQL (ParadeDB)
- **POSTGRES_DB**: 数据库名称
- **POSTGRES_USER**: 用户名
- **POSTGRES_PASSWORD**: 密码
- **DB_PORT**: 端口号

### API配置

#### Google Gemini
- **GOOGLE_API_KEYS_LIST**: Gemini API 密钥列表，支持多个密钥轮换
- **GEMINI_API_BASE_URL**: 自定义 Gemini API 端点（可选）
- **CUSTOM_GEMINI_URL**: 自定义 Gemini 端点（可选）
- **CUSTOM_GEMINI_API_KEY**: 自定义 Gemini API 密钥（可选）

### Discord配置

- **DISCORD_TOKEN**: Discord 机器人令牌（必需）
- **GUILD_ID**: 开发服务器ID（可选，用于快速同步命令）
- **DEVELOPER_USER_IDS**: 开发者用户ID列表（逗号分隔）
- **ADMIN_ROLE_IDS**: 管理员身份组ID列表（逗号分隔）
- **VITE_DISCORD_CLIENT_ID**: Discord OAuth 客户端ID（用于Web UI和21点游戏）
- **DISCORD_CLIENT_SECRET**: Discord OAuth 客户端密钥（用于Web UI）

### 其他配置

#### ComfyUI
- **COMFYUI_SERVER_ADDRESS**: ComfyUI 服务器地址
- **COMFYUI_WORKFLOW_PATH**: ComfyUI 工作流路径（可选）

#### 论坛搜索
- **FORUM_SEARCH_CHANNEL_IDS**: 需要进行RAG索引的论坛频道ID列表（逗号分隔）

#### 类脑币系统
- **COIN_REWARD_GUILD_IDS**: 发帖可获得奖励的服务器ID列表（逗号分隔）

---

### 数据库迁移
```bash
# 创建新的迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

---

## 常见问题

### Q: 如何启用/禁用聊天功能？
A: 可以通过两种方式：
1. 修改 `.env` 中的 `CHAT_ENABLED` 配置（全局紧急开关）
2. 使用 `/聊天设置` 命令，在管理面板中配置（更灵活，支持全局/频道/分类级别）

### Q: 暖贴功能如何配置？
A: 使用 `/聊天设置` 命令，点击"设置暖贴频道"按钮，选择要启用暖贴功能的论坛频道。

### Q: 如何添加新的AI工具？
A: 在 `src/chat/features/tools/functions/` 目录下创建新的Python文件，定义异步函数并使用 `@register_tool` 装饰器。

### Q: 如何配置多个Gemini API密钥？
A: 在 `.env` 文件中的 `GOOGLE_API_KEYS_LIST` 中，每行一个密钥，用双引号包裹所有密钥。

### Q: 数据存储在哪里？
A: 
- `data/chat.db`: SQLite数据库，存储聊天相关数据
- `data/world_book.sqlite3`: SQLite数据库，存储世界书数据
- `pgdata/`: PostgreSQL数据目录，存储ParadeDB数据

### Q: 如何查看日志？
A: 
- Docker部署: `docker-compose logs -f bot_app`
- 手动部署: 查看 `logs.txt` 文件

---

## 📄 许可证

本项目采用 GNU Affero General Public License v3.0 (AGPL-3.0) 许可证。详见 [LICENSE](LICENSE) 文件。

AGPL-3.0 是一个 copyleft 许可证，要求如果软件在网络服务器上运行并提供服务，则必须向用户公开源代码。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📮 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- echoer009@gmail.com

---

**Odysseia - 让社区更有温度 🌸**
