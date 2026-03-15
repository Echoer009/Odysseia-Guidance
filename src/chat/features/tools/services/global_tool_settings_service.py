# -*- coding: utf-8 -*-
"""
全局工具设置服务

管理全局工具的启用/禁用状态和系统保留状态。
数据存储在 SQLite global_settings 表中。
"""

import logging
from typing import List, Dict, Any, Optional

from src.chat.utils.database import chat_db_manager
from src.chat.features.tools.tool_metadata import TOOL_METADATA

log = logging.getLogger(__name__)

# 默认系统保留工具（向后兼容）
DEFAULT_PROTECTED_TOOLS = ["issue_user_warning"]


class GlobalToolSettingsService:
    """全局工具设置服务"""

    async def get_disabled_tools(self) -> List[str]:
        """
        获取全局禁用的工具列表。

        Returns:
            被全局禁用的工具名称列表
        """
        try:
            value = await chat_db_manager.get_global_setting("disabled_tools")
            if value:
                return [t.strip() for t in value.split(",") if t.strip()]
            return []
        except Exception as e:
            log.error(f"获取禁用工具列表失败: {e}", exc_info=True)
            return []

    async def set_disabled_tools(self, tool_names: List[str]) -> None:
        """
        设置全局禁用的工具列表。

        Args:
            tool_names: 要禁用的工具名称列表
        """
        value = ",".join(tool_names) if tool_names else ""
        await chat_db_manager.set_global_setting("disabled_tools", value)
        log.info(f"已更新全局禁用工具列表: {tool_names}")

    async def is_tool_disabled(self, tool_name: str) -> bool:
        """
        检查工具是否被全局禁用。

        Args:
            tool_name: 工具名称

        Returns:
            如果工具被全局禁用返回 True，否则返回 False
        """
        disabled_tools = await self.get_disabled_tools()
        return tool_name in disabled_tools

    async def toggle_tool_disabled(self, tool_name: str) -> bool:
        """
        切换工具的全局禁用状态。

        Args:
            tool_name: 工具名称

        Returns:
            切换后的状态（True 表示被禁用）
        """
        disabled_tools = await self.get_disabled_tools()
        if tool_name in disabled_tools:
            disabled_tools.remove(tool_name)
            await self.set_disabled_tools(disabled_tools)
            log.info(f"工具 '{tool_name}' 已全局启用")
            return False
        else:
            disabled_tools.append(tool_name)
            await self.set_disabled_tools(disabled_tools)
            log.info(f"工具 '{tool_name}' 已全局禁用")
            return True

    async def get_protected_tools(self) -> List[str]:
        """
        获取系统保留工具列表。

        系统保留工具是用户无法在自己的设置中禁用的工具。

        Returns:
            系统保留的工具名称列表
        """
        try:
            value = await chat_db_manager.get_global_setting("protected_tools")
            if value:
                return [t.strip() for t in value.split(",") if t.strip()]
            # 如果数据库中没有设置，返回默认值
            return DEFAULT_PROTECTED_TOOLS.copy()
        except Exception as e:
            log.error(f"获取系统保留工具列表失败: {e}", exc_info=True)
            return DEFAULT_PROTECTED_TOOLS.copy()

    async def set_protected_tools(self, tool_names: List[str]) -> None:
        """
        设置系统保留工具列表。

        Args:
            tool_names: 要设置为系统保留的工具名称列表
        """
        value = ",".join(tool_names) if tool_names else ""
        await chat_db_manager.set_global_setting("protected_tools", value)
        log.info(f"已更新系统保留工具列表: {tool_names}")

    async def is_tool_protected(self, tool_name: str) -> bool:
        """
        检查工具是否是系统保留的。

        Args:
            tool_name: 工具名称

        Returns:
            如果工具是系统保留的返回 True，否则返回 False
        """
        protected_tools = await self.get_protected_tools()
        return tool_name in protected_tools

    async def toggle_tool_protected(self, tool_name: str) -> bool:
        """
        切换工具的系统保留状态。

        Args:
            tool_name: 工具名称

        Returns:
            切换后的状态（True 表示是系统保留）
        """
        protected_tools = await self.get_protected_tools()
        if tool_name in protected_tools:
            protected_tools.remove(tool_name)
            await self.set_protected_tools(protected_tools)
            log.info(f"工具 '{tool_name}' 已取消系统保留")
            return False
        else:
            protected_tools.append(tool_name)
            await self.set_protected_tools(protected_tools)
            log.info(f"工具 '{tool_name}' 已设置为系统保留")
            return True

    async def get_all_tools_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有工具的完整状态。

        Returns:
            字典，键为工具名称，值为包含元数据、禁用状态和保留状态的字典
        """
        disabled_tools = await self.get_disabled_tools()
        protected_tools = await self.get_protected_tools()

        result = {}
        for tool_name, metadata in TOOL_METADATA.items():
            result[tool_name] = {
                "metadata": metadata,
                "is_disabled": tool_name in disabled_tools,
                "is_protected": tool_name in protected_tools,
            }

        return result

    async def get_tools_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        按类别获取所有工具及其状态。

        Returns:
            字典，键为类别名称，值为该类别下的工具列表
        """
        all_tools = await self.get_all_tools_status()

        categories: Dict[str, List[Dict[str, Any]]] = {}
        for tool_name, tool_info in all_tools.items():
            category = tool_info["metadata"].get("category", "通用")
            if category not in categories:
                categories[category] = []

            categories[category].append(
                {
                    "name": tool_name,
                    "display_name": tool_info["metadata"].get("name", tool_name),
                    "description": tool_info["metadata"].get("description", ""),
                    "emoji": tool_info["metadata"].get("emoji", "🔧"),
                    "is_disabled": tool_info["is_disabled"],
                    "is_protected": tool_info["is_protected"],
                }
            )

        return categories

    async def get_available_tools_for_user(self) -> List[str]:
        """
        获取用户可以在自己的设置中控制的工具列表。

        排除了全局禁用的工具和系统保留的工具。

        Returns:
            用户可控制的工具名称列表
        """
        disabled_tools = await self.get_disabled_tools()
        protected_tools = await self.get_protected_tools()

        return [
            name
            for name in TOOL_METADATA.keys()
            if name not in disabled_tools and name not in protected_tools
        ]


# 单例实例
global_tool_settings_service = GlobalToolSettingsService()
