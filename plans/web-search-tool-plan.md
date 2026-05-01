# 联网搜索工具 (Web Search) 方案

## 概述

为类脑娘添加联网能力，使用 SearXNG 自托管元搜索引擎作为后端，提供两个 AI 工具：**联网搜索** 和 **网页抓取**。AI 可以先搜索获取结果列表，再选择感兴趣的链接深入抓取内容。

```
用户提问 → AI 判断需要联网 → 调用 web_search → 获取搜索结果
                                            ↓ (如需深入)
                                        调用 web_scrape → 抓取网页正文
                                            ↓
                                        AI 综合回答用户
```

---

## 一、技术选型：SearXNG

### 1.1 为什么选 SearXNG

| 对比项 | SearXNG | Tavily | Brave Search | Serper.dev |
|--------|---------|--------|-------------|------------|
| 费用 | 完全免费 | 1000次/月后付费 | 2000次/月后付费 | 2500次/月后付费 |
| 部署 | Docker 自托管 | 零部署 | 零部署 | 零部署 |
| 结果质量 | 多引擎聚合 | AI 优化 | 独立引擎 | Google 代理 |
| 速度 | 2-5s | ~1s | ~1s | ~1s |
| 频率限制 | 无 | 有 | 有 | 有 |
| 隐私 | 不追踪 | 商业服务 | 商业服务 | 商业服务 |

### 1.2 SearXNG 工作原理

SearXNG 是**元搜索引擎**（metasearch engine），本身不建索引：

1. 收到搜索请求后，**并行向多个搜索引擎**（Google、Bing、DuckDuckGo、Wikipedia 等）发送请求
2. 汇总、去重、排序后返回统一结果
3. 支持 JSON 格式输出，方便程序调用

### 1.3 性能消耗

- **CPU/内存极低**：只是一个 Python Flask 请求转发服务，128MB 内存即可运行
- Docker 部署轻量，与现有 docker-compose 完美整合
- 依赖外部搜索引擎可用性，SearXNG 内置自动切换引擎机制

### 1.4 已知缺点

| 缺点 | 说明 | 应对 |
|------|------|------|
| 搜索延迟 | 需等待多引擎响应再聚合，通常 2-5 秒 | 可接受，Bot 回复本身有延迟 |
| 结果波动 | 不同引擎返回不同结果 | 多引擎聚合反而更全面 |
| 封 IP 风险 | 高频请求可能触发验证码 | 社区规模使用频率不高，问题不大 |
| 无 AI 优化 | 结果是原始搜索引擎返回 | AI 可以自行筛选和理解 |

### 1.5 扩展性设计

架构上预留多后端切换能力。搜索服务层使用抽象接口，后续可无缝添加 Tavily、Brave 等作为备选后端：

```
                    ┌──────────────┐
                    │ SearchService│  ← 统一接口
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ SearXNG  │ │  Tavily  │ │  Brave   │
        │ (默认)   │ │ (备选)   │ │ (备选)   │
        └──────────┘ └──────────┘ └──────────┘
```

---

## 二、架构设计

### 2.1 整体架构图

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────┐
│  AI 模型    │────▶│  工具系统             │────▶│  SearXNG    │
│  (Gemini等) │     │  web_search (搜索)   │     │  (Docker)   │
│             │     │  web_scrape (抓取)   │     │  :8888      │
└─────────────┘     └──────────────────────┘     └──────┬──────┘
                           │                            │
                           │  httpx (已有)              │ 聚合请求
                           ▼                            ▼
                    ┌──────────────┐            Google / Bing /
                    │  ScrapeService│            DuckDuckGo / ...
                    │  (正文提取)   │
                    └──────────────┘
```

### 2.2 目录结构

```
src/chat/features/web_search/
├── __init__.py
└── services/
    ├── __init__.py
    ├── search_service.py          # SearXNG 搜索服务
    └── scrape_service.py          # 网页正文抓取服务

src/chat/features/tools/functions/
├── web_search.py                  # AI 工具: 联网搜索 (新增)
├── web_scrape.py                  # AI 工具: 网页抓取 (新增)
├── search_forum.py                # 已有
├── ...
```

---

## 三、详细设计

### 3.1 Docker 部署 SearXNG

在 `docker-compose.yml` 中新增服务：

```yaml
# docker-compose.yml 新增
searxng:
  image: searxng/searxng:latest
  container_name: odysseia-searxng
  restart: unless-stopped
  ports:
    - "127.0.0.1:8888:8080"   # 仅本地访问，不对外暴露
  volumes:
    - ./data/searxng:/etc/searxng:rw
  environment:
    - SEARXNG_BASE_URL=http://localhost:8888/
  networks:
    - odysseia-network
```

SearXNG 配置文件 `data/searxng/settings.yml` 关键项：

```yaml
use_default_settings: true

search:
  formats:
    - html
    - json          # 启用 JSON API
  default_lang: ""  # 不限制语言，LLM 多语言能力强
  safe_search: 0    # 不过滤搜索结果

server:
  secret_key: "随机生成的密钥"
  limiter: false    # 内网使用不启用限流

engines:
  - name: google
    engine: google
    shortcut: g
  - name: bing
    engine: bing
    shortcut: b
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
  - name: wikipedia
    engine: wikipedia
    shortcut: wp
  - name: github
    engine: github
    shortcut: gh
```

### 3.2 搜索服务 (SearchService)

```python
# src/chat/features/web_search/services/search_service.py

class WebSearchService:
    """
    联网搜索服务。
    通过 SearXNG JSON API 执行搜索，返回结构化结果。
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def search(
        self,
        query: str,
        max_results: int = 5,
        categories: Optional[List[str]] = None,  # ["general", "images", "news", "it", "science"]
        engines: Optional[List[str]] = None,      # ["google", "bing", "duckduckgo"]
        timeout: float = 10.0,
    ) -> List[SearchResult]:
        """
        执行搜索查询。

        Args:
            query: 搜索关键词
            max_results: 最大返回结果数
            categories: 搜索类别（general/news/it/science 等）
            engines: 指定搜索引擎（google/bing/duckduckgo 等）
            timeout: 请求超时秒数

        Returns:
            SearchResult 列表，包含 title, url, snippet, engine 等字段
        """
        ...

    async def close(self):
        """关闭 HTTP 客户端"""
        ...
```

**返回数据结构：**

```python
@dataclass
class SearchResult:
    title: str           # 页面标题
    url: str             # 页面链接
    snippet: str         # 摘要片段
    engine: str          # 来源搜索引擎
    score: float         # SearXNG 评分
    category: str        # 搜索类别
```

### 3.3 网页抓取服务 (ScrapeService)

```python
# src/chat/features/web_search/services/scrape_service.py

class WebScrapeService:
    """
    网页正文抓取服务。
    抓取指定 URL，提取干净的正文内容。
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def scrape(
        self,
        url: str,
        max_length: int = 5000,
        timeout: float = 15.0,
    ) -> ScrapeResult:
        """
        抓取并提取网页正文。

        Args:
            url: 目标网页 URL
            max_length: 返回文本最大字符数（防止过大 token 消耗）
            timeout: 请求超时秒数

        Returns:
            ScrapeResult，包含 title, url, content, content_length 等字段
        """
        ...

    def _extract_content(self, html: str) -> str:
        """
        从 HTML 中提取正文内容。
        去除导航栏、页脚、脚本、样式等噪音，只保留核心文字。
        """
        ...

    async def close(self):
        """关闭 HTTP 客户端"""
        ...
```

**返回数据结构：**

```python
@dataclass
class ScrapeResult:
    title: str           # 页面标题
    url: str             # 页面 URL
    content: str         # 提取的正文内容（已截断至 max_length）
    content_length: int  # 原始内容长度（截断前）
    success: bool        # 是否成功抓取
    error: Optional[str] # 错误信息（如果失败）
```

**正文提取策略：**

优先级从高到低：
1. `<article>` 标签内容（语义化 HTML）
2. `<main>` 标签内容
3. `<div role="main">` 内容
4. 最大文本块启发式提取（找到文本密度最高的 div）
5. 全文 fallback（去除 script/style/nav/footer 后的纯文本）

依赖库选择：
- **首选**: `readability-lxml` + `lxml` — Mozilla Readability 算法的 Python 移植，专门为提取文章正文设计
- **备选**: `beautifulsoup4` + `lxml` — 手动实现提取逻辑

### 3.4 AI 工具：联网搜索 (web_search)

```python
# src/chat/features/tools/functions/web_search.py

class WebSearchParams(BaseModel):
    """联网搜索参数"""
    query: str = Field(
        ...,
        description="搜索关键词。用于查询互联网上的信息。",
    )
    max_results: int = Field(
        default=5,
        description="返回结果数量限制，最多10条。",
    )

@tool_metadata(
    name="联网搜索",
    description="搜索互联网获取信息，返回相关网页列表",
    emoji="🌐",
    category="查询",
)
async def web_search(params: WebSearchParams, **kwargs) -> List[str]:
    """
    搜索互联网获取信息。

    返回格式：
    - 返回一个字符串列表，每条格式为：`标题\n摘要\n链接`。
    - 你可以从中选择有价值的链接，使用 web_scrape 工具进一步获取详细内容。
    """
    ...
```

### 3.5 AI 工具：网页抓取 (web_scrape)

```python
# src/chat/features/tools/functions/web_scrape.py

class WebScrapeParams(BaseModel):
    """网页抓取参数"""
    url: str = Field(
        ...,
        description="要抓取内容的网页 URL。必须以 http:// 或 https:// 开头。",
    )
    max_length: int = Field(
        default=5000,
        description="返回内容的最大字符数。默认5000字符。",
    )

@tool_metadata(
    name="网页抓取",
    description="抓取指定网页的正文内容，用于深入了解某个链接的详细信息",
    emoji="📄",
    category="查询",
)
async def web_scrape(params: WebScrapeParams, **kwargs) -> str:
    """
    抓取指定网页的正文内容。

    适用于在 web_search 搜索结果中，发现需要深入了解的链接时使用。
    会自动提取网页核心文字内容，去除导航、广告等噪音。
    """
    ...
```

---

## 四、安全与限制

### 4.1 频率限制

| 限制项 | 值 | 说明 |
|--------|---|------|
| 搜索频率 | 每用户每分钟 3 次 | 防止滥用 |
| 抓取频率 | 每用户每分钟 5 次 | 抓取通常在搜索后使用 |
| 单次搜索结果数 | 最多 10 条 | 防止返回过多数据 |
| 抓取内容长度 | 最大 8000 字符 | 防止 token 消耗过大 |
| 搜索超时 | 10 秒 | SearXNG 请求超时 |
| 抓取超时 | 15 秒 | 网页请求超时 |

### 4.2 URL 安全

- 仅允许 `http://` 和 `https://` 协议
- 禁止访问内网地址（`localhost`、`127.0.0.1`、`10.*`、`192.168.*`、`172.16-31.*`）— SSRF 防护
- 禁止访问 Bot 自身服务（SearXNG、Ollama、PostgreSQL 等）

### 4.3 工具调用流程安全

- 两个工具遵循现有工具系统的全局禁用/用户禁用机制
- 无需特殊安全加固（不像 `issue_user_warning` 需要强制 user_id 校验）

---

## 五、配置

### 5.1 环境变量 (.env)

```env
# === SearXNG 搜索引擎 ===
SEARXNG_URL=http://searxng:8080    # Docker 内部网络地址
# SEARXNG_URL=http://localhost:8888 # 本地开发地址

# 可选：搜索服务配置
WEB_SEARCH_MAX_RESULTS=5
WEB_SEARCH_TIMEOUT=10
WEB_SCRAPE_MAX_LENGTH=5000
WEB_SCRAPE_TIMEOUT=15
```

### 5.2 常量配置 (config.py)

```python
# SearXNG 搜索引擎
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888")
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_SEARCH_TIMEOUT = float(os.getenv("WEB_SEARCH_TIMEOUT", "10"))
WEB_SCRAPE_MAX_LENGTH = int(os.getenv("WEB_SCRAPE_MAX_LENGTH", "5000"))
WEB_SCRAPE_TIMEOUT = float(os.getenv("WEB_SCRAPE_TIMEOUT", "15"))
```

### 5.3 新增依赖 (requirements.txt)

```
readability-lxml>=0.8.0    # 网页正文提取
lxml>=5.0.0                # XML/HTML 解析（可能已有）
```

---

## 六、文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **修改** | `docker-compose.yml` | 新增 SearXNG 服务定义 |
| **新增** | `data/searxng/settings.yml` | SearXNG 配置文件 |
| **新增** | `src/chat/features/web_search/__init__.py` | 包初始化 |
| **新增** | `src/chat/features/web_search/services/__init__.py` | 服务包初始化 |
| **新增** | `src/chat/features/web_search/services/search_service.py` | SearXNG 搜索服务 |
| **新增** | `src/chat/features/web_search/services/scrape_service.py` | 网页抓取服务 |
| **新增** | `src/chat/features/tools/functions/web_search.py` | AI 工具: 联网搜索 |
| **新增** | `src/chat/features/tools/functions/web_scrape.py` | AI 工具: 网页抓取 |
| **修改** | `src/config.py` 或 `src/chat/config/chat_config.py` | 新增 SearXNG 相关常量 |
| **修改** | `.env.example` | 新增 SearXNG 配置示例 |
| **修改** | `requirements.txt` | 新增 readability-lxml、lxml |

> **注意**: `tool_loader.py` 无需修改，新工具文件放在 `functions/` 目录下会被自动发现和加载。

---

## 七、实施顺序

### Phase 1: 基础设施

1. 在 `docker-compose.yml` 中添加 SearXNG 服务
2. 创建 `data/searxng/settings.yml` 配置文件
3. 启动 SearXNG，验证 JSON API 可用
4. 在 `requirements.txt` 中添加 `readability-lxml`

### Phase 2: 服务层

1. 创建 `src/chat/features/web_search/services/` 目录
2. 实现 `SearchService`（SearXNG HTTP 调用 + 结果解析）
3. 实现 `ScrapeService`（网页抓取 + 正文提取）
4. 添加配置常量到 config

### Phase 3: AI 工具

1. 创建 `web_search.py` 工具函数
2. 创建 `web_scrape.py` 工具函数
3. 验证工具被 `tool_loader` 自动发现和加载
4. 测试 AI 调用链路：搜索 → 筛选 → 抓取 → 回答

### Phase 4: 安全加固与优化

1. 添加频率限制（per-user rate limiting）
2. 添加 SSRF 防护（内网地址过滤）
3. 添加错误处理和降级逻辑
4. 更新 `.env.example`

### Phase 5: 测试

1. 单元测试：SearchService、ScrapeService
2. 集成测试：完整搜索 → 抓取流程
3. 边界测试：超时、空结果、无效 URL、SSRF 防护

---

## 八、后续扩展方向

| 方向 | 说明 | 优先级 |
|------|------|--------|
| 多搜索后端 | 添加 Tavily/Brave 作为备选后端，配置切换 | 低 - SearXNG 够用 |
| 搜索缓存 | 相同 query 缓存搜索结果，减少外部请求 | 中 - 高频场景有用 |
| 图片搜索 | 利用 SearXNG 的图片搜索类别 | 低 - 按需添加 |
| 新闻搜索 | 利用 SearXNG 的 news 类别 | 低 - 按需添加 |
| 搜索统计 | 记录搜索次数、热门查询等 | 低 - 运营分析 |
