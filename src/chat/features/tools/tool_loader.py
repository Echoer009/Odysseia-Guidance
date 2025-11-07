import os
import importlib
import inspect
import logging
from typing import List, Dict, Callable

log = logging.getLogger(__name__)


def load_tools_from_directory(directory: str) -> (List[Callable], Dict[str, Callable]):
    """
    动态地从指定目录加载所有工具函数。

    这个加载器会遍历目录下的所有 Python 文件（非 `__init__.py`），
    并导入其中定义的异步函数作为工具。

    Args:
        directory: 包含工具函数模块的目录路径。

    Returns:
        一个元组，包含：
        - available_tools: 一个可供模型使用的函数对象列表。
        - tool_map: 一个从函数名到函数对象的字典，用于执行。
    """
    available_tools = []
    tool_map = {}

    log.info(f"--- [工具加载器]: 开始从 '{directory}' 目录加载工具 ---")

    for filename in os.listdir(directory):
        if filename.endswith(".py") and not filename.startswith("__init__"):
            module_name = filename[:-3]
            # 构建完整的模块路径，例如: src.chat.features.tools.functions.get_user_avatar
            module_path = f"{directory.replace('/', '.')}.{module_name}"

            try:
                module = importlib.import_module(module_path)
                log.info(f"成功导入模块: {module_path}")

                # 遍历模块中的所有成员，查找异步函数
                for name, func in inspect.getmembers(
                    module, inspect.iscoroutinefunction
                ):
                    if not name.startswith("_"):  # 忽略私有函数
                        log.info(f"  -> 发现工具函数: '{func.__name__}'")
                        available_tools.append(func)
                        tool_map[func.__name__] = func

            except ImportError as e:
                log.error(f"导入模块 {module_path} 时失败: {e}", exc_info=True)

    log.info(f"--- [工具加载器]: 加载完成。共发现 {len(available_tools)} 个工具 ---")
    return available_tools, tool_map
