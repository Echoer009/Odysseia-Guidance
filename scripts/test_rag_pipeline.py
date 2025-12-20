import asyncio
import logging
import os
import sys

# 配置日志记录器，以便我们可以看到服务中的日志输出
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

# 将项目根目录添加到 Python 路径中
# 这样我们就可以像在主应用中一样导入我们的模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.features.tutorial_search.services.tutorial_search_service import (
    tutorial_search_service,
)


async def main():
    """
    执行RAG管道的端到端测试。
    """
    print("--- 开始 RAG 端到端测试 ---")

    # 模拟一个典型的用户问题
    test_query = "我的酒馆启动失败怎么办？"
    print(f"测试问题: '{test_query}'")

    print("\n正在调用 tutorial_search_service.search()...")

    # 调用我们的核心服务
    # 我们传入一个虚拟的 user_id 用于日志记录
    final_context = await tutorial_search_service.search(
        query=test_query, user_id="test_user_001"
    )

    print("\n--- 服务返回的最终上下文 ---")
    print(final_context)
    print("-----------------------------\n")

    print("测试完成。")
    print("请检查控制台输出的上下文是否相关，")
    print("并检查 'logs/tutorial_rag_trace.log' 文件以获取详细的执行追踪。")


if __name__ == "__main__":
    asyncio.run(main())
