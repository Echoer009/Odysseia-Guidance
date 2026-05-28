# gather_context 工具改造方案

## 概述

将 prompt 中所有**高 token 占用、每次请求都变**的动态上下文（RAG 数据、对话记忆、个人印象摘要、最新对话块）从 prompt 注入改为**单一工具 `gather_context` 按需加载**。模型完全自主决定是否调用及调用范围。

**目标**：最大化 DeepSeek prefix cache 命中率，同时统一所有 Provider 的上下文加载策略。

### 改造前后对比

**改造前**（每次消息都注入全部动态数据到 prompt）：
```
Layer 1: Jailbreak + System Prompt          → 缓存命中
Layer 2: 好感度 + 用户画像 + 个人印象摘要     → 好感度/摘要变化时断缓存
Layer 3: 频道历史                             → 每条消息都变，缓存断裂
Layer 4: World Book RAG + 对话记忆 + 最新块   → 每次不同
Layer 5: 用户输入                             → 每次不同
```

**改造后**（动态数据通过工具按需获取）：
```
Layer 1: Jailbreak + System Prompt          → 缓存命中 ✅
Layer 2: 用户画像（仅名称/个性/背景/偏好）    → 同用户缓存命中 ✅
Layer 3: 频道历史 + 好感度（单独注入）        → 缓存断裂
Layer 4: 用户输入                            → 每次不同
（RAG/记忆/印象 → 模型按需调用 gather_context 工具获取）
```

---

## 一、新增文件

### 1.1 `src/chat/features/tools/functions/gather_context.py`

**工具设计**：单一工具，通过 `scope` 参数控制返回内容。

```python
class GatherContextParams(BaseModel):
    scope: Literal["impression", "conversation", "knowledge_base", "conversation_memory", "all"] = Field(
        default="all",
        description=(
            "查询范围："
            "impression=你对用户的印象和了解；"
            "conversation=你和用户最近的对话记录；"
            "knowledge_base=搜索知识库（需提供query）；"
            "conversation_memory=搜索历史对话记忆（需提供query）；"
            "all=以上全部。"
            "如果不确定需要什么，使用 all。"
        ),
    )
    query: Optional[str] = Field(
        None,
        description="搜索关键词（scope 为 knowledge_base 或 conversation_memory 时建议提供，scope 为 all 时可作为搜索依据）",
    )
```

**工具元数据**：
```python
@tool_metadata(
    name="获取上下文",
    description="获取关于当前用户的上下文信息，包括你对ta的印象、最近的对话记录、知识库搜索结果、历史对话记忆等。根据 scope 参数选择需要的信息。",
    emoji="🧠",
    category="查询",
)
```

**内部逻辑按 scope 分发**：

| scope | 调用的服务 | 需要的 kwargs |
|-------|-----------|-------------|
| `impression` | `world_book_service.get_profile_by_discord_id()` → 提取 `personal_summary` | `user_id` |
| `conversation` | `conversation_block_service.get_latest_block_content()` | `user_id` |
| `knowledge_base` | `world_book_service.find_entries()` + `_format_world_book_entries()` | `user_id`, `guild_id`, `user_name`, `fallback_query` |
| `conversation_memory` | `conversation_memory_search_service.search()` + `format_blocks_for_context()` | `user_id`, `fallback_query` |
| `all` | 以上全部 | 全部 |

**返回格式**：
```python
{
    "scope": "all",
    "results": {
        "impression": "对用户的印象摘要文本（如有）",
        "conversation": "最新对话块文本（如有）",
        "knowledge_base": "格式化后的知识库搜索结果（如有）",
        "conversation_memory": "格式化后的对话记忆搜索结果（如有）",
    }
}
```

**关键依赖导入**：
```python
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.features.personal_memory.services.conversation_block_service import conversation_block_service
from src.chat.features.personal_memory.services.conversation_memory_search_service import conversation_memory_search_service
from src.chat.services.prompt_service import prompt_service  # 复用 _format_world_book_entries
```

**kwargs 依赖**（由 `tool_service.execute_tool_call` 注入）：

| kwargs key | 来源 | 当前是否已注入 | 需要新增 |
|------------|------|--------------|---------|
| `user_id` | `execute_tool_call` 参数 | ✅ 已有 | - |
| `guild_id` | `channel.guild.id` | ✅ 已有 | - |
| `user_name` | chat_service 传入 | ❌ | **需新增** |
| `fallback_query` | chat_service 传入 | ❌ | **需新增** |
| `channel_context` | chat_service 传入 | ❌ | **需新增** |

**关于 `fallback_query`**：当模型调用 `scope="all"` 但未提供 `query` 时，工具需要一个合理的默认搜索词。chat_service 已构建 `rag_query`（用户消息 + 回复内容），将其作为 `fallback_query` 传入。

**关于 `channel_context`**：`world_book_service.find_entries()` 需要 `conversation_history` 参数作为搜索上下文。由于频道历史已在 prompt 中，工具可以从 kwargs 获取它。

---

## 二、修改文件

### 2.1 `src/chat/services/chat_service.py`（主要改动）

**文件路径**：`src/chat/services/chat_service.py`
**方法**：`handle_chat_message`（lines 121-434）

#### 改动 A：移除 RAG/记忆预取（lines 149-243）

**移除以下代码块**：

```python
# line 152-154: 移除 personal_summary 提取
personal_summary = None
if user_profile_data:
    personal_summary = user_profile_data.get("personal_summary")

# lines 176-189: 移除 world_book_entries 预取
rag_query = user_content
if replied_content:
    rag_query = f"{replied_content}\n{user_content}"
log.info(f"为 RAG 搜索生成的查询: '{rag_query}'")
world_book_entries = await world_book_service.find_entries(...)

# lines 194-243: 移除 conversation_memory 和 latest_block 预取
conversation_memory_text = None
latest_block_content = None
if user_profile_data:
    ...
    conversation_memory_blocks = await conversation_memory_search_service.search(...)
    ...
    latest_block_content = await conversation_block_service.get_latest_block_content(...)
```

**保留以下代码**：
- `user_profile_data = await world_book_service.get_profile_by_discord_id(author.id)` (line 149-151) — 仍需判断用户是否有 profile
- `channel_context = await get_context_service().get_formatted_channel_history_new(...)` (lines 164-171) — 频道历史仍在 prompt 中
- `await personal_memory_service.check_and_create_block_before_reply(user_id=author.id)` (lines 199-201) — **副作用必须保留**，确保对话块在工具检索前创建
- `affection_status = await affection_service.get_affection_status(author.id)` (line 246) — 好感度仍在 prompt 中
- `persona_style = await persona_preference_service.get_persona_style(...)` (line 247)

**新增**：构建 `rag_query`（为 `gather_context` 工具提供 fallback query）
```python
# 构建备用搜索查询（供 gather_context 工具使用）
rag_query = user_content
if replied_content:
    rag_query = f"{replied_content}\n{user_content}"
```

#### 改动 B：更新 `build_chat_prompt` 调用（lines 300-318）

**移除/置空以下参数**：
```python
messages = await prompt_service.build_chat_prompt(
    user_name=author.display_name,
    message=user_content,
    replied_message=replied_content,
    images=image_data_list if image_data_list else None,
    channel_context=channel_context,
    world_book_entries=None,              # ← 改为 None
    affection_status=affection_status,    # ← 保留
    guild_name=guild_name,
    location_name=location_name,
    personal_summary=None,                # ← 改为 None
    user_profile_data=user_profile_data,  # ← 保留（画像仍在 prompt）
    model_name=current_model,
    channel=message.channel,
    conversation_memory=None,             # ← 改为 None
    latest_block=None,                    # ← 改为 None
    output_format=output_format,
    persona_style=persona_style,
)
```

#### 改动 C：更新 tool_executor（lines 329-345）

**新增 kwargs 传递**：
```python
async def tool_executor(call, **kwargs):
    ...
    return await ai_service.tool_service.execute_tool_call(
        call,
        channel=message.channel,
        user_id=author.id,
        user_id_for_settings=user_id_for_settings,
        user_name=author.display_name,     # ← 新增
        fallback_query=rag_query,          # ← 新增
        channel_context=channel_context,   # ← 新增（供 find_entries 使用）
    )
```

---

### 2.2 `src/chat/features/tools/services/tool_service.py`

**文件路径**：`src/chat/features/tools/services/tool_service.py`
**方法**：`execute_tool_call`（lines 211-476）

#### 改动：扩展签名和 kwargs 注入（line 211-218, 303-355）

**签名新增参数**：
```python
async def execute_tool_call(
    self,
    tool_call: Union[types.FunctionCall, Dict[str, Any]],
    channel: Optional[discord.TextChannel] = None,
    user_id: Optional[int] = None,
    log_detailed: bool = False,
    user_id_for_settings: Optional[str] = None,
    user_name: Optional[str] = None,          # ← 新增
    fallback_query: Optional[str] = None,      # ← 新增
    channel_context: Optional[List[Dict]] = None,  # ← 新增
) -> types.Part:
```

**在 kwargs 注入区域（约 line 355 后）新增**：
```python
if user_name is not None:
    tool_args["user_name"] = user_name

if fallback_query is not None:
    tool_args["fallback_query"] = fallback_query

if channel_context is not None:
    tool_args["channel_context"] = channel_context
```

---

### 2.3 `src/chat/services/prompt_service.py`（主要改动）

**文件路径**：`src/chat/services/prompt_service.py`

#### 改动 A：`_build_chat_prompt_default`（lines 311-779）

**移除以下注入块**（RAG + 三层记忆）：

| 行号 | 内容 | 操作 |
|------|------|------|
| 430-439 | World Book RAG 注入 (`<world_book_context>`) | **删除** |
| 441-476 | 三层记忆合并注入 (`<personal_memory>` + `<conversation_memory>` + `<latest_conversation>`) | **删除** |

**拆分好感度与用户画像**（lines 478-548）：

当前代码将好感度和画像合并为 `<attitude_and_background>` 块。需要拆分为：

1. **用户画像**（保留在当前位置，channel history 之前）：
```python
# 4. 用户画像注入（单独注入，不包含好感度）
user_profile_prompt = ""
if user_profile_data:
    # ... 原有的 source_data 解析逻辑不变 ...
    if profile_details:
        user_profile_prompt = "\n" + "\n".join(profile_details)

if user_profile_prompt:
    final_conversation.append({
        "role": "user",
        "parts": [f'<background user="{user_name}">\n这是关于 {user_name} 的一些背景信息，你在与ta互动时应该了解这些\n{user_profile_prompt.lstrip()}\n</background>'],
    })
    final_conversation.append({"role": "model", "parts": ["这事我知道了"]})
```

2. **频道历史注入**（保持不变，lines 550-553）

3. **好感度注入**（移到频道历史之后）：
```python
# 频道历史后：好感度注入（单独注入）
affection_prompt = affection_status.get("prompt", "").replace("用户", user_name) if affection_status else ""
if affection_prompt:
    final_conversation.append({
        "role": "user",
        "parts": [f'<attitude user="{user_name}">\n态度: {affection_prompt}\n</attitude>'],
    })
    final_conversation.append({"role": "model", "parts": ["收到"]})
```

**最终 default 构建顺序**：
```
1. Jailbreak (user+model)                           ← 固定
2. System Prompt (user+model)                       ← 固定
3. 帖子首楼 (user+model, 如有)                       ← 半固定
4. 用户画像 <background> (user+model)                ← 同用户缓存
5. 频道历史 (user+model 多轮)                        ← 动态（缓存断裂点）
6. 好感度 <attitude> (user+model)                    ← 动态
7. 回复上下文 (user+model, 如有)                     ← 动态
8. 最终指令 (合并到 model 消息)                       ← 半固定
9. 用户输入 (user)                                   ← 动态
```

#### 改动 B：`_build_chat_prompt_cache_optimized`（lines 781-1218）

同样的改动逻辑：

**移除以下注入块**：

| 行号 | 内容 | 操作 |
|------|------|------|
| 964-971 | 个人印象摘要 (`<personal_memory>`) | **删除** |
| 995-1003 | World Book RAG (`<world_book_context>`) | **删除** |
| 1005-1026 | 对话记忆 + 最新对话块 (`<conversation_memory>` + `<latest_conversation>`) | **删除** |

**拆分好感度与用户画像**（lines 907-962）：

当前 Layer 2 中 `<attitude_and_background>` 包含好感度 + 画像。拆分为：

1. **用户画像**（保留在 Layer 2，lines 914-949 的画像解析逻辑不变）：
   - 保留 `<background>` 块在 Layer 2
   - 移除好感度部分

2. **好感度**（移到频道历史之后，在 Layer 3 回复上下文之后）：
   - 新增独立的 `<attitude>` 块

**最终 cache-optimized 构建顺序**：
```
Layer 1 — 固定锚点（缓存命中）
  user:  Jailbreak
  model: Response
  user:  SYSTEM_PROMPT
  model: "我在线啦"
  user:  帖子首楼（如有）
  model: "了解了"

Layer 2 — 用户画像（同用户缓存命中）
  user:  <background>（仅画像）
  model: "这事我知道了"

Layer 3 — 动态（缓存断裂）
  user+model: 频道历史上下文
  user:  好感度 <attitude>
  model: "收到"
  user:  回复上下文（如有）
  model: "收到"

Layer 4 — 最终
  model: 最终指令（system_info）
  user:  当前用户输入 + 图片
```

---

## 三、改动总览

### 文件改动清单

| 文件 | 改动类型 | 具体改动 |
|------|---------|---------|
| `src/chat/features/tools/functions/gather_context.py` | **新建** | 单一工具实现，按 scope 调用不同 service |
| `src/chat/services/chat_service.py` | **修改** | 移除 RAG/记忆预取；更新 build_chat_prompt 调用参数；tool_executor 新增 kwargs |
| `src/chat/services/prompt_service.py` | **修改** | 两个构建方法移除 RAG/记忆注入；拆分好感度与画像；好感度移到频道历史后 |
| `src/chat/features/tools/services/tool_service.py` | **修改** | execute_tool_call 新增 user_name/fallback_query/channel_context 参数注入 |

### 不需要改动的文件

| 文件 | 原因 |
|------|------|
| `src/chat/features/world_book/services/world_book_service.py` | 工具直接调用现有方法 |
| `src/chat/features/personal_memory/services/conversation_memory_search_service.py` | 工具直接调用现有方法 |
| `src/chat/features/personal_memory/services/conversation_block_service.py` | 工具直接调用现有方法 |
| `src/chat/features/personal_memory/services/personal_memory_service.py` | check_and_create_block_before_reply 保留在 chat_service |
| `src/chat/features/affection/service/affection_service.py` | 仍在 chat_service 中预取 |
| `src/chat/features/tools/tool_metadata.py` | 直接使用现有装饰器模式 |
| `src/chat/features/tools/tool_loader.py` | 自动发现新工具文件 |

---

## 四、风险评估

### 4.1 模型不调用工具的风险

**风险**：模型可能不在该调用时调用 `gather_context`，导致回复缺乏个性化（不知道用户印象、没有对话记忆、没有知识库信息）。

**缓解**：
- 工具 description 写清楚每种 scope 的用途
- 用户画像和好感度仍在 prompt 中，保证基本的用户认知
- 频道历史仍在 prompt 中，保证对话连贯性
- 上线后监控工具调用率，如果过低可考虑在 system prompt 中增加引导

### 4.2 延迟增加

**风险**：工具调用需要额外 1 次 API 往返（模型决定调用 → 执行工具 → 模型基于结果回复）。

**缓解**：
- DeepSeek 支持在同一次响应中调用多个工具，scope="all" 只需 1 次工具调用
- 对于简单闲聊，模型不调用工具，反而更快（prompt 更短）
- 监控 p95 延迟变化

### 4.3 Gemini 兼容性

**风险**：Gemini 的工具调用格式与 DeepSeek 不同。

**缓解**：现有工具框架已支持多格式（`ToolDeclaration.to_openai_format()` / `to_gemini_tools()`），新工具自动适配。

---

## 五、实施步骤

### Phase 1：创建 gather_context 工具
1. 新建 `src/chat/features/tools/functions/gather_context.py`
2. 实现 `GatherContextParams` Pydantic 模型
3. 实现 `gather_context` 函数，按 scope 分发逻辑
4. 复用 `prompt_service._format_world_book_entries()` 格式化 RAG 结果

### Phase 2：修改 tool_service.py
1. `execute_tool_call` 新增 `user_name`、`fallback_query`、`channel_context` 参数
2. 在 kwargs 注入区域添加这三个参数的注入逻辑

### Phase 3：修改 chat_service.py
1. 移除 RAG/记忆预取代码块
2. 保留 `check_and_create_block_before_reply` 副作用
3. 新增 `rag_query` 构建（为工具提供 fallback query）
4. 更新 `build_chat_prompt` 调用（RAG 参数置 None）
5. 更新 `tool_executor` 闭包（新增 kwargs 传递）

### Phase 4：修改 prompt_service.py — default 构建
1. 删除 World Book RAG 注入（lines 430-439）
2. 删除三层记忆注入（lines 441-476）
3. 拆分 `<attitude_and_background>` 为独立 `<background>` 和 `<attitude>`
4. 将 `<attitude>` 移到频道历史之后

### Phase 5：修改 prompt_service.py — cache-optimized 构建
1. 删除个人印象摘要注入（lines 964-971）
2. 删除 World Book RAG 注入（lines 995-1003）
3. 删除对话记忆 + 最新块注入（lines 1005-1026）
4. 拆分 `<attitude_and_background>` 为独立块
5. 将 `<attitude>` 移到频道历史之后

### Phase 6：测试验证
1. 启动 bot，发送简单消息 → 模型应不调用工具直接回复
2. 发送涉及用户的问题 → 模型应调用 `gather_context(scope="impression")` 或 `scope="all"`
3. 发送知识性问题 → 模型应调用 `gather_context(scope="knowledge_base", query="...")`
4. 验证 DeepSeek 缓存命中率是否提升
5. 验证 Gemini 工具调用正常工作

---

## 六、可清理项（Phase 7，可选）

改造完成后，以下代码/参数可以考虑清理：

1. **`build_chat_prompt` 签名**：`world_book_entries`、`personal_summary`、`conversation_memory`、`latest_block` 参数可移除或标记为 deprecated
2. **`chat_service.py` 导入**：`conversation_memory_search_service` 导入可移除（不再直接使用）
3. **`_format_world_book_entries` 方法**：保留，被 `gather_context` 工具复用
