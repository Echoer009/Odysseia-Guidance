"""
工具元数据装饰器

允许工具函数定义自己的显示信息（名称、描述、emoji）。
"""

import functools
from typing import Callable, Optional, Dict, Any

from src.chat.config.chat_config import DISABLED_TOOLS, HIDDEN_TOOLS

# 全局工具元数据注册表
TOOL_METADATA: Dict[str, Dict[str, Any]] = {}


def tool_metadata(
    name: str,
    description: str,
    emoji: str = "🔧",
    category: str = "通用",
):
    """
    装饰器：为工具函数添加元数据

    Args:
        name: 工具的显示名称
        description: 工具的简短描述（给用户看）
        emoji: 工具的 emoji 图标
        category: 工具类别（用于分组显示）
    """

    def decorator(func: Callable) -> Callable:
        # 注册工具元数据
        TOOL_METADATA[func.__name__] = {
            "name": name,
            "description": description,
            "emoji": emoji,
            "category": category,
        }

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def get_tool_metadata(tool_name: str) -> Optional[Dict[str, Any]]:
    """获取工具的元数据"""
    return TOOL_METADATA.get(tool_name)


def get_all_tools_metadata() -> Dict[str, Dict[str, Any]]:
    """获取所有工具的元数据（自动过滤掉禁用的和隐藏的工具）"""
    return {
        name: meta
        for name, meta in TOOL_METADATA.items()
        if name not in DISABLED_TOOLS and name not in HIDDEN_TOOLS
    }


def get_tools_by_category(category: str) -> Dict[str, Dict[str, Any]]:
    """按类别获取工具（自动过滤掉禁用的和隐藏的工具）"""
    return {
        name: meta
        for name, meta in TOOL_METADATA.items()
        if meta.get("category") == category
        and name not in DISABLED_TOOLS
        and name not in HIDDEN_TOOLS
    }
