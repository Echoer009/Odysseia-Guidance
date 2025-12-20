import logging
from src.chat.features.tutorial_search.services.tutorial_search_service import (
    tutorial_search_service,
)

log = logging.getLogger(__name__)


async def query_tutorial_knowledge_base(query: str, **kwargs) -> str:
    """
    从专业知识库中获取关于 SillyTavern (酒馆) 和类脑社区的权威教程。

    触发关键词:
    - **核心**: 酒馆, SillyTavern, 类脑, 角色卡, 预设, 世界书, 宏
    - **技术**: 安装, 更新, 备份, 部署, 报错, API, Gemini, Claude, DeepSeek, 代理, Docker, Git。
    - **社区**: 规则, 频道, 答疑, 涩图, 等级。

    当问题包含上述关键词，或与这些主题高度相关时，优先使用此工具。
    **备用调用**: 如果问题不含明确关键词，但你对答案不确定且主题可能相关，也应调用此工具核实。
    参数 query 应为用户的原始问题。
    """
    log.info(f"工具 'query_tutorial_knowledge_base' 被调用，查询: '{query}'")

    # 工具的职责非常简单：直接调用专门的 Service 来完成所有复杂工作。
    # 这使得工具本身保持干净、解耦，并且避免了循环依赖。
    context = await tutorial_search_service.search(query)

    # 如果搜索服务未能找到任何内容，直接返回其提示信息
    if not context or "没有找到" in context:
        return context

    # --- 专用提示词包装 ---
    # 为 RAG 返回的上下文添加一层严格的指令，确保 AI 忠实地使用提供的链接
    prompt_wrapper = f"""
请严格根据以下提供的参考资料来回答问题。

**核心指令**:
1.  **忠实引用**: 当你引用或提及任何教程时，必须使用下面资料中提供的、与之对应的 Markdown 格式链接，例如 `[教程标题](链接)`。
2.  **禁止修改**: 绝对不允许以任何形式修改、替换或自行创造任何 URL 链接。链接必须与资料中的原文一字不差。
3.  **内容为王**: 你的回答应该完全基于这些资料的内容。如果资料无法解答，请明确告知。

--- 参考资料 ---
{context}
--- 结束 ---
"""
    return prompt_wrapper
