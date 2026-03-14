# -*- coding: utf-8 -*-
"""
Schema 工具模块

提供 Pydantic 模型到各 LLM 兼容 Schema 的转换功能。

核心功能：
1. 从 Pydantic 模型提取 JSON Schema（保留 description）
2. 将 JSON Schema 转换为 Gemini 兼容格式
3. 从函数签名和 Pydantic 模型生成完整的工具 Schema
"""

import inspect
from typing import (
    Any,
    Callable,
    Dict,
    Literal,
    Optional,
    Type,
    Union,
    get_origin,
    get_args,
)

from pydantic import BaseModel
import logging

log = logging.getLogger(__name__)


# ==================== 类型映射 ====================

JSON_TYPE_TO_GEMINI = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


# ==================== 核心转换函数 ====================


def convert_to_gemini_schema(pydantic_schema: dict) -> dict:
    """
    将 Pydantic JSON Schema 转换为 Gemini 兼容格式

    Gemini 的特殊要求：
    - 类型名必须大写（STRING, INTEGER, OBJECT 等）
    - anyOf 需要转换为 any_of
    - $ref 引用需要展开（Gemini 不支持 $ref）

    Args:
        pydantic_schema: Pydantic 模型的 JSON Schema（从 model_json_schema() 获取）

    Returns:
        Gemini 兼容的 Schema 字典
    """
    result = {}

    # 处理 anyOf（Optional[...] 或 Union[...] 类型）
    if "anyOf" in pydantic_schema:
        non_null_types = [
            t for t in pydantic_schema["anyOf"] if t.get("type") != "null"
        ]
        result["nullable"] = True

        if non_null_types:
            if len(non_null_types) > 1:
                # 多个类型的 Union，使用 any_of
                result["any_of"] = [_convert_type_schema(t) for t in non_null_types]
            else:
                # 单个类型的 Optional
                result.update(_convert_type_schema(non_null_types[0]))

    # 处理普通类型
    elif "type" in pydantic_schema:
        result.update(_convert_type_schema(pydantic_schema))

    # 复制 description（关键！这是我们要保留的信息）
    if "description" in pydantic_schema:
        result["description"] = pydantic_schema["description"]

    # 复制 default 值
    if "default" in pydantic_schema:
        result["default"] = pydantic_schema["default"]

    # 处理 enum
    if "enum" in pydantic_schema:
        result["enum"] = pydantic_schema["enum"]

    return result


def _convert_type_schema(schema: dict) -> dict:
    """
    转换单个类型定义

    Args:
        schema: 包含 type 字段的 schema 片段

    Returns:
        转换后的 schema 片段
    """
    result = {}

    schema_type = schema.get("type")
    if not schema_type:
        return result

    # 基础类型转换
    if schema_type in JSON_TYPE_TO_GEMINI:
        result["type"] = JSON_TYPE_TO_GEMINI[schema_type]

    # 处理嵌套 object
    if schema_type == "object" and "properties" in schema:
        result["type"] = "OBJECT"
        result["properties"] = {}
        for prop_name, prop_schema in schema["properties"].items():
            result["properties"][prop_name] = convert_to_gemini_schema(prop_schema)

        # 处理 required 字段（Gemini 也支持）
        if "required" in schema:
            result["required"] = schema["required"]

    # 处理 array
    if schema_type == "array" and "items" in schema:
        result["type"] = "ARRAY"
        result["items"] = convert_to_gemini_schema(schema["items"])

    # 处理 enum（Literal 类型会被转换为 enum）
    if "enum" in schema:
        result["enum"] = schema["enum"]

    return result


# ==================== 从函数提取 Schema ====================


def extract_function_schema(
    func: Callable,
    param_models: Optional[Dict[str, Type[BaseModel]]] = None,
    function_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    从函数签名和 Pydantic 模型提取完整的工具 Schema

    这个函数会：
    1. 解析函数签名的类型注解
    2. 如果参数是 Pydantic 模型，提取其 JSON Schema
    3. 生成标准 JSON Schema 格式的参数定义

    Args:
        func: 要提取 schema 的函数
        param_models: 可选的参数名 → Pydantic 模型映射
        function_description: 可选的函数描述（默认使用 docstring）

    Returns:
        包含 name, description, parameters 的字典
    """
    sig = inspect.signature(func)
    parameters_schema = {"type": "object", "properties": {}, "required": []}
    param_models = param_models or {}

    for param_name, param in sig.parameters.items():
        # 跳过 **kwargs 和 *args
        if param.kind in (param.VAR_KEYWORD, param.VAR_POSITIONAL):
            continue

        # 跳过内部参数（以 _ 开头）
        if param_name.startswith("_"):
            continue

        # 获取参数类型
        param_type = param.annotation
        param_schema = {}

        # 检查是否有对应的 Pydantic 模型
        if param_name in param_models:
            # 使用 Pydantic 模型生成 schema
            model_class = param_models[param_name]
            param_schema = _pydantic_model_to_param_schema(model_class)
        elif param_type != inspect.Parameter.empty:
            # 从类型注解推断 schema
            param_schema = _type_to_schema(param_type)

        # 如果有默认值，标记为可选
        if param.default != inspect.Parameter.empty:
            param_schema["default"] = param.default
        else:
            # 没有默认值且不是 Optional，添加到 required
            if not _is_optional_type(param_type):
                parameters_schema["required"].append(param_name)

        parameters_schema["properties"][param_name] = param_schema

    return {
        "name": func.__name__,
        "description": function_description or _extract_description(func),
        "parameters": parameters_schema,
    }


def _pydantic_model_to_param_schema(model_class: Type[BaseModel]) -> dict:
    """
    将 Pydantic 模型转换为参数 schema

    Args:
        model_class: Pydantic 模型类

    Returns:
        参数 schema 字典
    """
    schema = model_class.model_json_schema()
    return convert_to_gemini_schema(schema)


def _type_to_schema(python_type: Type) -> dict:
    """
    将 Python 类型转换为 JSON Schema

    Args:
        python_type: Python 类型注解

    Returns:
        JSON Schema 字典
    """
    # 处理 Optional[...]
    if _is_optional_type(python_type):
        inner_type = _get_optional_inner_type(python_type)
        schema = _type_to_schema(inner_type)
        schema["nullable"] = True
        return schema

    origin = get_origin(python_type)

    # 处理 Literal[...] -> 转换为 enum
    if origin is Literal:
        args = get_args(python_type)
        # Literal 的所有值应该是同一类型，取第一个值的类型
        if args:
            first_arg = args[0]
            if isinstance(first_arg, str):
                type_str = "STRING"
            elif isinstance(first_arg, int):
                type_str = "INTEGER"
            elif isinstance(first_arg, float):
                type_str = "NUMBER"
            elif isinstance(first_arg, bool):
                type_str = "BOOLEAN"
            else:
                type_str = "STRING"
            return {"type": type_str, "enum": list(args)}
        return {"type": "STRING"}

    # 处理 List[...]
    if origin is list:
        args = get_args(python_type)
        item_type = args[0] if args else str
        return {
            "type": "ARRAY",
            "items": _type_to_schema(item_type),
        }

    # 处理 Dict[...]
    if origin is dict:
        return {"type": "OBJECT"}

    # 处理 Pydantic 模型
    if isinstance(python_type, type) and issubclass(python_type, BaseModel):
        return _pydantic_model_to_param_schema(python_type)

    # 基础类型映射
    type_map = {
        str: "STRING",
        int: "INTEGER",
        float: "NUMBER",
        bool: "BOOLEAN",
        list: "ARRAY",
        dict: "OBJECT",
    }

    gemini_type = type_map.get(python_type, "STRING")
    return {"type": gemini_type}


def _is_optional_type(python_type: Type) -> bool:
    """检查是否是 Optional 类型"""
    origin = get_origin(python_type)
    if origin is Union:
        args = get_args(python_type)
        return type(None) in args
    return False


def _get_optional_inner_type(python_type: Type) -> Type:
    """获取 Optional 的内部类型"""
    args = get_args(python_type)
    for arg in args:
        if arg is not type(None):
            return arg
    return str


def _extract_description(func: Callable) -> str:
    """从函数 docstring 提取描述"""
    doc = func.__doc__
    if not doc:
        return ""
    # 返回完整的 docstring，去除前后空白
    return doc.strip()


# ==================== 辅助函数：从模块提取 Pydantic 模型 ====================


def find_pydantic_models_in_module(module) -> Dict[str, Type[BaseModel]]:
    """
    从模块中提取所有 Pydantic 模型

    查找规则：
    1. 模型名以函数名开头（如 SearchForumFilters 对应 search_forum）
    2. 或者模型名包含 "Params"、"Filters"、"Args" 等后缀

    Args:
        module: Python 模块对象

    Returns:
        模型名 → 模型类的字典
    """
    models = {}

    for name, obj in inspect.getmembers(module, inspect.isclass):
        # 检查是否是 Pydantic 模型
        if not issubclass(obj, BaseModel):
            continue

        # 排除 BaseModel 本身
        if obj is BaseModel:
            continue

        models[name] = obj

    return models


def match_models_to_function(
    func_name: str,
    models: Dict[str, Type[BaseModel]],
) -> Dict[str, Type[BaseModel]]:
    """
    将 Pydantic 模型匹配到函数参数

    匹配规则：
    1. 模型名 = 函数名 + "Params" / "Filters" / "Args" / "Input"
    2. 模型名 = 函数名的驼峰形式 + 上述后缀

    Args:
        func_name: 函数名
        models: 可用的 Pydantic 模型字典

    Returns:
        参数名 → 模型类的映射
    """
    result = {}

    # 生成可能的模型名
    func_name_camel = _snake_to_camel(func_name)
    suffixes = ["Params", "Filters", "Args", "Input", ""]

    for suffix in suffixes:
        # 尝试 snake_case + suffix
        model_name = f"{func_name}{suffix}"
        if model_name in models:
            result["filters"] = models[model_name]  # 默认映射到 filters 参数
            break

        # 尝试 CamelCase + suffix
        model_name = f"{func_name_camel}{suffix}"
        if model_name in models:
            result["filters"] = models[model_name]
            break

    return result


def _snake_to_camel(name: str) -> str:
    """将 snake_case 转换为 CamelCase"""
    return "".join(word.capitalize() for word in name.split("_"))
