import logging
from src.chat.features.tutorial_search.services.tutorial_search_service import (
    tutorial_search_service,
)
from src.chat.services.prompt_service import prompt_service

log = logging.getLogger(__name__)


async def query_tutorial_knowledge_base(query: str, **kwargs) -> str:
    """
    专用于查询 SillyTavern(酒馆)、类脑社区及公益站的**教程、指南与报错解决方案**。

    触发关键词:
    - **核心**: 酒馆, SillyTavern, 类脑, 公益站, 角色卡, 预设, 世界书, 宏
    - **技术**: 安装, 更新, 备份, 部署, 报错, API, Gemini, Claude, DeepSeek, 代理, Docker, Git, 免费, 公益站
    - **社区**: 规则, 频道, 答疑。

    **注意**: 日常问题无需使用。
    参数 `query` 应为用户的原始问题。
    """
    log.info(f"工具 'query_tutorial_knowledge_base' 被调用，查询: '{query}'")

    # 1. 从 kwargs 中提取 user_id 和 thread_id
    user_id = kwargs.get("user_id", "N/A")
    thread_id = kwargs.get("thread_id")

    # 2. 调用搜索服务，获取原始的、结构化的教程文档列表
    docs = await tutorial_search_service.search(
        query, user_id=str(user_id), thread_id=thread_id
    )

    # 3. 将原始文档列表和 thread_id 传递给 prompt_service 进行专业的上下文格式化
    #    prompt_service 内部会处理 docs 为空的情况，并包裹上必要的指令。
    formatted_context = prompt_service.format_tutorial_context(docs, thread_id)

    # 4. 返回由 prompt_service 精心构建的、带有明确来源标注和行为指令的最终上下文
    return formatted_context
