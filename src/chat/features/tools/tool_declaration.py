# -*- coding: utf-8 -*-
"""
通用工具声明模块

定义与 LLM API 无关的工具声明格式。

设计原则：
1. 使用标准 JSON Schema 作为参数描述格式（所有 LLM 都能理解）
2. 保留对实际函数的引用（运行时调用）
3. 支持可选的元数据（emoji, category 等，用于 UI 展示）
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolDeclaration:
    """
    通用工具声明 - 与具体 LLM API 无关

    这个类包含两部分信息：
    1. Schema 信息：告诉 AI 这个工具做什么、参数是什么
    2. 执行信息：实际要调用的函数

    Attributes:
        name: 工具名称（对应函数名）
        description: 工具描述（给 AI 看的）
        parameters: JSON Schema 格式的参数定义
        function: 实际执行的异步函数
        emoji: 可选的 emoji 图标（UI 展示用）
        category: 可选的分类（UI 展示用）
        display_name: 可选的显示名称（UI 展示用，默认使用 name）
    """

    # 必需字段
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema 格式
    function: Callable

    # 可选元数据（UI 展示用）
    emoji: str = "🔧"
    category: str = "通用"
    display_name: Optional[str] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.display_name is None:
            self.display_name = self.name

    def to_openai_format(self) -> Dict[str, Any]:
        """
        转换为 OpenAI Tools 格式

        OpenAI 格式：
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": { ... JSON Schema ... }
            }
        }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_claude_format(self) -> Dict[str, Any]:
        """
        转换为 Claude Tools 格式

        Claude 格式：
        {
            "name": "...",
            "description": "...",
            "input_schema": { ... JSON Schema ... }
        }
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（用于序列化）

        注意：不包含 function，因为函数不能直接序列化
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "emoji": self.emoji,
            "category": self.category,
            "display_name": self.display_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], function: Callable) -> "ToolDeclaration":
        """
        从字典创建 ToolDeclaration

        Args:
            data: 包含工具声明的字典
            function: 要绑定的函数

        Returns:
            ToolDeclaration 实例
        """
        return cls(
            name=data["name"],
            description=data["description"],
            parameters=data["parameters"],
            function=function,
            emoji=data.get("emoji", "🔧"),
            category=data.get("category", "通用"),
            display_name=data.get("display_name"),
        )


@dataclass
class ToolRegistry:
    """
    工具注册表 - 管理所有工具声明

    提供工具的注册、查询、过滤等功能。
    """

    # 工具声明列表
    declarations: List[ToolDeclaration] = field(default_factory=list)

    # 函数名 → 函数的映射（用于执行）
    function_map: Dict[str, Callable] = field(default_factory=dict)

    # 禁用的工具名列表
    disabled_tools: List[str] = field(default_factory=list)

    # 隐藏的工具名列表
    hidden_tools: List[str] = field(default_factory=list)

    def register(self, declaration: ToolDeclaration) -> None:
        """
        注册一个工具

        Args:
            declaration: 工具声明
        """
        self.declarations.append(declaration)
        self.function_map[declaration.name] = declaration.function

    def get_function(self, name: str) -> Optional[Callable]:
        """
        获取工具函数

        Args:
            name: 工具名称

        Returns:
            工具函数，如果不存在返回 None
        """
        return self.function_map.get(name)

    def get_declaration(self, name: str) -> Optional[ToolDeclaration]:
        """
        获取工具声明

        Args:
            name: 工具名称

        Returns:
            工具声明，如果不存在返回 None
        """
        for decl in self.declarations:
            if decl.name == name:
                return decl
        return None

    def get_all_declarations(self) -> List[ToolDeclaration]:
        """获取所有工具声明"""
        return self.declarations

    def get_available_declarations(
        self,
        exclude_disabled: bool = True,
        exclude_hidden: bool = True,
    ) -> List[ToolDeclaration]:
        """
        获取可用的工具声明（过滤掉禁用和隐藏的）

        Args:
            exclude_disabled: 是否排除禁用的工具
            exclude_hidden: 是否排除隐藏的工具

        Returns:
            过滤后的工具声明列表
        """
        result = []
        for decl in self.declarations:
            if exclude_disabled and decl.name in self.disabled_tools:
                continue
            if exclude_hidden and decl.name in self.hidden_tools:
                continue
            result.append(decl)
        return result

    def get_by_category(self, category: str) -> List[ToolDeclaration]:
        """
        按分类获取工具

        Args:
            category: 分类名称

        Returns:
            该分类下的工具声明列表
        """
        return [d for d in self.declarations if d.category == category]

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """
        转换为 OpenAI Tools 格式

        Returns:
            OpenAI 格式的工具列表
        """
        return [d.to_openai_format() for d in self.get_available_declarations()]

    def to_claude_tools(self) -> List[Dict[str, Any]]:
        """
        转换为 Claude Tools 格式

        Returns:
            Claude 格式的工具列表
        """
        return [d.to_claude_format() for d in self.get_available_declarations()]

    def __len__(self) -> int:
        """返回工具数量"""
        return len(self.declarations)

    def __contains__(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self.function_map
