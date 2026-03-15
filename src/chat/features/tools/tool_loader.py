# -*- coding: utf-8 -*-
"""
工具加载器模块

动态地从指定目录加载所有工具函数，并生成通用工具声明。

返回：
- tool_declarations: List[ToolDeclaration] - 通用工具声明列表（包含 JSON Schema）
- tool_map: Dict[str, Callable] - 函数名到函数的映射（用于执行）

注意：工具的启用/禁用状态现在由 GlobalToolSettingsService 在运行时控制，
不再在加载时过滤。所有工具都会被加载，在执行时检查禁用状态。
"""

import os
import importlib
import inspect
import logging
from typing import Dict, Callable, List, Tuple

from src.chat.features.tools.tool_declaration import ToolDeclaration
from src.chat.features.tools.tool_metadata import get_tool_metadata
from src.chat.features.tools.schema_utils import extract_function_schema

log = logging.getLogger(__name__)


def load_tools_from_directory(
    directory: str,
) -> Tuple[List[ToolDeclaration], Dict[str, Callable]]:
    """
    动态地从指定目录加载所有工具函数，并生成通用工具声明。

    这个加载器会：
    1. 遍历目录下的所有 Python 文件（非 `__init__.py`）
    2. 导入其中定义的异步函数作为工具
    3. 检测函数签名中的 Pydantic 模型，自动生成带 description 的 schema
    4. 创建通用工具声明（ToolDeclaration）

    Args:
        directory: 包含工具函数模块的目录路径。

    Returns:
        一个元组，包含：
        - tool_declarations: 通用工具声明列表（包含 JSON Schema 和函数引用）
        - tool_map: 一个从函数名到函数对象的字典，用于执行。
    """
    tool_declarations: List[ToolDeclaration] = []
    tool_map: Dict[str, Callable] = {}

    log.info(f"--- [工具加载器]: 开始从 '{directory}' 目录加载工具 ---")
    log.info(f"--- [工具加载器]: 注意 - 工具启用/禁用状态由运行时配置控制 ---")

    for filename in os.listdir(directory):
        if filename.endswith(".py") and not filename.startswith("__init__"):
            module_name = filename[:-3]

            # 构建完整的模块路径
            directory_str = str(directory).replace("\\", "/").replace("/", ".")
            module_path = f"{directory_str}.{module_name}"

            try:
                module = importlib.import_module(module_path)
                log.info(f"成功导入模块: {module_path}")

                # 遍历模块中的所有成员，查找异步函数
                for name, func in inspect.getmembers(
                    module, inspect.iscoroutinefunction
                ):
                    if name.startswith("_"):  # 忽略私有函数
                        continue

                    log.info(f"  -> 发现工具函数: '{name}'")

                    # 获取函数的元数据（如果有）
                    metadata = get_tool_metadata(name) or {}

                    # 提取函数 schema
                    # extract_function_schema 会自动检测 Pydantic 模型并生成带 description 的 schema
                    # 注意：不传递 metadata 的 description，因为那是给配置面板用的
                    # AI 应该看到的是函数的 docstring 和 Pydantic 模型字段的 description
                    func_schema = extract_function_schema(
                        func=func,
                        function_description=None,  # 使用函数的 docstring
                    )

                    # 创建通用工具声明
                    declaration = ToolDeclaration(
                        name=func_schema["name"],
                        description=func_schema["description"],
                        parameters=func_schema["parameters"],
                        function=func,
                        emoji=metadata.get("emoji", "🔧"),
                        category=metadata.get("category", "通用"),
                        display_name=metadata.get("name", func_schema["name"]),
                    )

                    tool_declarations.append(declaration)
                    tool_map[name] = func

            except ImportError as e:
                log.error(f"导入模块 {module_path} 时失败: {e}", exc_info=True)
            except Exception as e:
                log.error(f"处理模块 {module_path} 时出错: {e}", exc_info=True)

    log.info(f"--- [工具加载器]: 加载完成。共发现 {len(tool_declarations)} 个工具 ---")
    return tool_declarations, tool_map


# ==================== 向后兼容 ====================


def load_tools_from_directory_legacy(
    directory: str,
) -> Tuple[List[Callable], Dict[str, Callable]]:
    """
    旧版加载器（向后兼容）

    直接返回函数对象列表，不生成 schema。
    这个函数保留用于过渡期，后续版本将移除。

    Args:
        directory: 包含工具函数模块的目录路径。

    Returns:
        一个元组，包含：
        - available_tools: 一个可供模型使用的函数对象列表。
        - tool_map: 一个从函数名到函数对象的字典，用于执行。
    """
    available_tools = []
    tool_map = {}

    log.warning(
        "使用旧版工具加载器 (load_tools_from_directory_legacy)，"
        "建议迁移到新版 (load_tools_from_directory)"
    )

    for filename in os.listdir(directory):
        if filename.endswith(".py") and not filename.startswith("__init__"):
            module_name = filename[:-3]

            module_path = f"{directory.replace('/', '.')}.{module_name}"

            try:
                module = importlib.import_module(module_path)
                log.info(f"成功导入模块: {module_path}")

                for name, func in inspect.getmembers(
                    module, inspect.iscoroutinefunction
                ):
                    if not name.startswith("_"):
                        log.info(f"  -> 发现工具函数: '{func.__name__}'")
                        available_tools.append(func)
                        tool_map[func.__name__] = func

            except ImportError as e:
                log.error(f"导入模块 {module_path} 时失败: {e}", exc_info=True)

    log.info(f"--- [工具加载器]: 加载完成。共发现 {len(available_tools)} 个工具 ---")
    return available_tools, tool_map
