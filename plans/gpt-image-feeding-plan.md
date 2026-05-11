# GPT Image 2 投喂生图功能

## 功能概述

用户使用 `/投喂` 上传图片 → AI 判断是否是正常食物 → 如果是，调用 GPT Image 2 生成类脑娘吃该食物的图片，替换 embed 原图 → 如果不是，正常吐槽不画图 → 生图失败则 fallback 到原来的默认贴纸。

## 已确认信息

- **API**: 公益站单点 `https://gpt.goldenglow.us.ci/v1`，单 key，无需轮换
- **生图方式**: 传入食物图片 + 类脑娘参考图，让 GPT Image 2 生成"类脑娘吃该食物"的图
- **非食物**: 保持现状（吐槽 + sticker 贴图）
- **Fallback**: 生图失败 → 回退到原 sticker_url

## 食物判定方案：复用现有 AI 评价流程

**不需要额外的 API 调用或工具。** 当前 `/投喂` 已经把图片发给 AI 并要求评价，AI 返回 `<affection:X;coins:Y>`。我们只需要在同一个 prompt 的输出格式中增加 `is_food` 字段。

### 原流程

```
用户图片 → AI 评价（含图片识别）→ 返回评价文本 + <affection:X;coins:Y>
```

### 新流程

```
用户图片 → AI 评价（含图片识别）→ 返回评价文本 + <is_food:是/否;food_desc:简短描述;affection:X;coins:Y>
                                                                 ↓
                                                    解析 is_food 字段
                                                                 ↓
                                              is_food=是 → 触发生图
                                              is_food=否 → 跳过生图
```

### 为什么不用单独的工具/调用

1. **AI 已经在看图片了** — 当前 feeding_prompt 已经要求 AI 识别图片内容并评价，额外调一次是浪费
2. **零额外延迟** — 只是在同一个 AI 回复中多输出两个字段
3. **上下文一致** — 评价文本和 is_food 判定来自同一次推理，不会出现矛盾

### 判定依据

现有 prompt 中的规则已经很明确：
- 现实食物 → coins 200-300
- 动漫食物 → coins 50-150
- 非食物 → coins 5-15

AI 在评价时已经做了"是不是食物"的判断，我们只是让它把结论显式输出。

## 修改清单

### 1. 新建 `src/chat/services/gpt_image_service.py`

轻量服务类，用 `httpx.AsyncClient` 调用 OpenAI Images API：

```python
class GPTImageService:
    def __init__(self):
        # 读取 GPT_IMAGE_API_KEY / GPT_IMAGE_BASE_URL
        # 下载并缓存类脑娘参考图的 bytes
        self._reference_image_bytes: Optional[bytes] = None

    async def generate_feeding_image(
        self,
        food_image_bytes: bytes,
        food_mime_type: str,
        food_description: str,
    ) -> Optional[bytes]:
        """
        调用 GPT Image 2 生成类脑娘吃食物的图片。
        成功返回图片 bytes，失败返回 None。
        """
        # 策略优先级：
        # A) images/edits 传食物图 + prompt（含参考图描述）
        # B) 如果 A 不支持多图，用 images/generations 纯文本 prompt
        # C) 请求失败 → log + return None
```

### 2. 修改 `src/chat/config/chat_config.py`

新增配置块：

```python
# --- GPT Image 2 配置 ---
GPT_IMAGE_CONFIG = {
    "API_KEY": os.getenv("GPT_IMAGE_API_KEY", ""),
    "BASE_URL": os.getenv("GPT_IMAGE_BASE_URL", "https://api.openai.com/v1"),
    "MODEL": os.getenv("GPT_IMAGE_MODEL", "gpt-image-2"),
    "SIZE": "1024x1024",
    "QUALITY": "medium",
    "TIMEOUT": 60,
    "REFERENCE_IMAGE_URL": os.getenv(
        "GPT_IMAGE_REFERENCE_URL",
        FEEDING_CONFIG["RESPONSE_IMAGE_URL"],  # 默认用现有 sticker 做参考
    ),
}
```

### 3. 修改 feeding_prompt（`chat_config.py` line 391-408）

在输出格式中新增 `is_food` 和 `food_desc` 字段：

```
## 输出格式
在评价文本的最后，请严格按照以下格式：
`<is_food:是/否;food_desc:简短食物描述;affection:好感度;coins:类脑币>`

示例：
哇这个蛋糕看起来超好吃！<is_food:是;food_desc:巧克力蛋糕;affection:+8;coins:+250>
这个拉面画得很好看但终究是二次元的<is_food:是;food_desc:动漫拉面;affection:+4;coins:+80>
欸...这是石头吧？我又不是什么都吃<is_food:否;food_desc:无;affection:+1;coins:+5>
```

### 4. 修改 `src/chat/features/affection/cogs/feeding_cog.py`

核心改动在 AI 评价完成后（约 line 140 之后）：

```python
# 新的正则：解析扩展格式
# 原：<affection:X;coins:Y>
# 新：<is_food:是/否;food_desc:xxx;affection:X;coins:Y>

# 解析新增字段
is_food = parsed_group.get("is_food") == "是"
food_desc = parsed_group.get("food_desc", "")

# --- 生图逻辑（仅在 unrestricted 频道 + 是食物 时触发）---
generated_image_bytes = None
if is_food and is_unrestricted:
    generated_image_bytes = await gpt_image_service.generate_feeding_image(
        food_image_bytes=image_bytes,
        food_mime_type=image.content_type,
        food_description=food_desc,
    )

# 构建 embed image 部分
if generated_image_bytes:
    # 生图成功：用 attachment 嵌入（不依赖 URL，不会失效）
    gen_file = discord.File(
        io.BytesIO(generated_image_bytes),
        filename="feeding_generated.png"
    )
    embed.set_image(url="attachment://feeding_generated.png")
    attachments = [file, gen_file]  # file = 原始食物缩略图
else:
    # fallback 或非食物：原来的 sticker 逻辑（保持不变）
    if is_unrestricted:
        embed.set_image(url=sticker_url)
    attachments = [file]
```

### 5. 更新 `.env.example`

```env
# --- GPT Image 2 投喂生图 ---
GPT_IMAGE_API_KEY="sk-xxx"
GPT_IMAGE_BASE_URL="https://gpt.goldenglow.us.ci/v1"
GPT_IMAGE_MODEL="gpt-image-2"
```

## Fallback 链路

```
用户投喂食物图片
    → AI 评价（已有逻辑，新增 is_food/food_desc 输出）
    → 解析 is_food
        → 否 → 保持现状（sticker 或无大图）
        → 是 → 调用 GPT Image 2
            → 成功 → attachment 嵌入（无 URL 过期风险）
            → 失败（超时/限流/API错误）→ log.warning + 用原 sticker_url
```

## 关键设计决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 食物判定方式 | 复用现有 AI 评价 | 零额外延迟，AI 已在识别图片 |
| 生图触发条件 | is_food=是 + unrestricted 频道 | 非食物不需要生图，受限频道保持简洁 |
| 图片嵌入方式 | discord.File attachment | 不依赖外部 URL，不会失效 |
| Fallback | 静默回退到 sticker_url | 用户无感，不影响体验 |
| Key 管理 | 单 key，无轮换 | 公益站单点 |
| 类脑娘参考图 | 配置 URL，启动时缓存 | 避免每次生图都下载 |

## 待确认

- [ ] 类脑娘参考图用哪张？默认用 `FEEDING_CONFIG["RESPONSE_IMAGE_URL"]` 的 sticker 图，还是另选？
- [ ] 生图是否只在 unrestricted 频道触发？还是所有频道都生？
