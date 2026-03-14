# -*- coding: utf-8 -*-
"""
LLM 适配器模块

提供将通用工具声明转换为各 LLM API 所需格式的适配器。

支持的 LLM：
- Google Gemini（需要类型转换）
- OpenAI（直接使用 JSON Schema）
- DeepSeek（OpenAI 兼容）
- Claude（直接使用 JSON Schema，字段名略有不同）
"""

from typing import Any, Dict, List, Union

from .tool_declaration import ToolDeclaration

import logging

log = logging.getLogger(__name__)


# ==================== Gemini 适配器 ====================


def _dict_to_gemini_schema(schema_dict: Dict[str, Any]):
    """
    将字典格式的 schema 递归转换为 google.genai.types.Schema 对象

    Args:
        schema_dict: 字典格式的 schema

    Returns:
        google.genai.types.Schema 对象
    """
    from google.genai import types

    # 处理类型字符串转换
    type_value = schema_dict.get("type")
    if isinstance(type_value, str):
        # 将字符串类型转换为 types.Type 枚举
        type_map = {
            "string": types.Type.STRING,
            "STRING": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "INTEGER": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "NUMBER": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "BOOLEAN": types.Type.BOOLEAN,
            "array": types.Type.ARRAY,
            "ARRAY": types.Type.ARRAY,
            "object": types.Type.OBJECT,
            "OBJECT": types.Type.OBJECT,
        }
        type_value = type_map.get(
            type_value.upper() if isinstance(type_value, str) else type_value
        )

    # 递归处理 properties
    properties = None
    if "properties" in schema_dict:
        properties = {}
        for prop_name, prop_schema in schema_dict["properties"].items():
            if isinstance(prop_schema, dict):
                properties[prop_name] = _dict_to_gemini_schema(prop_schema)
            else:
                properties[prop_name] = prop_schema

    # 递归处理 items（数组元素类型）
    items = None
    if "items" in schema_dict:
        items_dict = schema_dict["items"]
        if isinstance(items_dict, dict):
            items = _dict_to_gemini_schema(items_dict)

    # 递归处理 anyOf/any_of（Union 类型）
    # 支持两种键名：anyOf（JSON Schema 原生）和 any_of（Gemini 格式）
    any_of = None
    any_of_key = "anyOf" if "anyOf" in schema_dict else "any_of"
    if any_of_key in schema_dict:
        any_of = []
        for sub_schema in schema_dict[any_of_key]:
            if isinstance(sub_schema, dict):
                any_of.append(_dict_to_gemini_schema(sub_schema))

    return types.Schema(
        type=type_value,
        description=schema_dict.get("description"),
        properties=properties,
        required=schema_dict.get("required"),
        items=items,
        any_of=any_of,
        nullable=schema_dict.get("nullable"),
        default=schema_dict.get("default"),
        enum=schema_dict.get("enum"),
        min_items=schema_dict.get("minItems"),
        max_items=schema_dict.get("maxItems"),
        min_length=schema_dict.get("minLength"),
        max_length=schema_dict.get("maxLength"),
        minimum=schema_dict.get("minimum"),
        maximum=schema_dict.get("maximum"),
        pattern=schema_dict.get("pattern"),
    )


def to_gemini_function_declaration(declaration: ToolDeclaration):
    """
    将单个 ToolDeclaration 转换为 Gemini FunctionDeclaration

    Args:
        declaration: 通用工具声明

    Returns:
        google.genai.types.FunctionDeclaration
    """
    try:
        from google.genai import types
    except ImportError:
        raise ImportError("需要安装 google-genai: pip install google-genai")

    # 转换参数 schema 为 Gemini Schema 对象
    gemini_parameters = _dict_to_gemini_schema(declaration.parameters)

    return types.FunctionDeclaration(
        name=declaration.name,
        description=declaration.description,
        parameters=gemini_parameters,
    )


def to_gemini_tools(declarations: List[ToolDeclaration]) -> List:
    """
    将 ToolDeclaration 列表转换为 Gemini Tools 格式

    Args:
        declarations: 工具声明列表

    Returns:
        包含单个 Tool 的列表（Gemini 的 Tool 包含多个 FunctionDeclaration）
    """
    try:
        from google.genai import types
    except ImportError:
        raise ImportError("需要安装 google-genai: pip install google-genai")

    fn_declarations = []
    for decl in declarations:
        try:
            fn_decl = to_gemini_function_declaration(decl)
            fn_declarations.append(fn_decl)
        except Exception as e:
            log.error(f"转换工具 '{decl.name}' 为 Gemini 格式时出错: {e}")
            continue

    # Gemini 的 Tool 是一个包含多个 FunctionDeclaration 的容器
    return [types.Tool(function_declarations=fn_declarations)]


# ==================== OpenAI 适配器 ====================


def to_openai_tools(declarations: List[ToolDeclaration]) -> List[Dict[str, Any]]:
    """
    将 ToolDeclaration 列表转换为 OpenAI Tools 格式

    OpenAI 直接使用 JSON Schema，几乎不需要转换。

    Args:
        declarations: 工具声明列表

    Returns:
        OpenAI 格式的工具列表
    """
    return [decl.to_openai_format() for decl in declarations]


# ==================== DeepSeek 适配器 ====================


def to_deepseek_tools(declarations: List[ToolDeclaration]) -> List[Dict[str, Any]]:
    """
    将 ToolDeclaration 列表转换为 DeepSeek Tools 格式

    DeepSeek 兼容 OpenAI API，所以格式相同。

    Args:
        declarations: 工具声明列表

    Returns:
        DeepSeek/OpenAI 格式的工具列表
    """
    return to_openai_tools(declarations)


# ==================== Claude 适配器 ====================


def to_claude_tools(declarations: List[ToolDeclaration]) -> List[Dict[str, Any]]:
    """
    将 ToolDeclaration 列表转换为 Claude Tools 格式

    Claude 使用 input_schema 而不是 parameters，但格式相同。

    Args:
        declarations: 工具声明列表

    Returns:
        Claude 格式的工具列表
    """
    return [decl.to_claude_format() for decl in declarations]


# ==================== 通用适配器 ====================


def to_llm_tools(
    declarations: List[ToolDeclaration],
    llm_type: str,
) -> Union[List[Dict[str, Any]], List]:
    """
    根据LLM 类型转换工具声明

    Args:
        declarations: 工具声明列表
        llm_type: LLM 类型，支持 "gemini", "openai", "deepseek", "claude"

    Returns:
        对应 LLM 格式的工具列表

    Raises:
        ValueError: 不支持的 LLM 类型
    """
    adapters = {
        "gemini": to_gemini_tools,
        "openai": to_openai_tools,
        "deepseek": to_deepseek_tools,
        "claude": to_claude_tools,
        # 别名
        "google": to_gemini_tools,
        "anthropic": to_claude_tools,
    }

    llm_type_lower = llm_type.lower()
    if llm_type_lower not in adapters:
        raise ValueError(
            f"不支持的 LLM 类型: {llm_type}。支持的类型: {list(adapters.keys())}"
        )

    return adapters[llm_type_lower](declarations)
