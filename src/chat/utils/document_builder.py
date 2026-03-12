# -*- coding: utf-8 -*-
"""
文档构造工具模块

用于构建 RAG 向量化的结构化文档文本。
支持论坛帖子、社区成员、通用知识等多种文档类型。
"""

from typing import Optional


def build_forum_thread_document(
    thread_name: str,
    content: str,
    author_name: Optional[str] = None,
    category_name: Optional[str] = None,
) -> str:
    """
    构建论坛帖子的结构化文档文本。

    采用 JSON 风格的结构化格式，便于模型理解文档结构。

    Args:
        thread_name: 帖子标题
        content: 帖子正文内容
        author_name: 作者名称（可选）
        category_name: 分类/版块名称（可选）

    Returns:
        结构化的文档文本字符串

    Example:
        >>> build_forum_thread_document(
        ...     thread_name="如何使用类脑娘的RAG功能",
        ...     content="类脑娘支持混合搜索...",
        ...     author_name="小明",
        ...     category_name="教程分享"
        ... )
        '标题: 如何使用类脑娘的RAG功能\\n分类: 教程分享\\n作者: 小明\\n\\n内容:\\n类脑娘支持混合搜索...'
    """
    parts = [f"标题: {thread_name}"]

    if category_name:
        parts.append(f"分类: {category_name}")

    if author_name and author_name != "未知作者":
        parts.append(f"作者: {author_name}")

    # 添加空行分隔元数据和正文
    parts.append("")
    parts.append(f"内容:\n{content}")

    return "\n".join(parts)


def build_forum_thread_document_simple(
    thread_name: str,
    content: str,
) -> str:
    """
    构建论坛帖子的简单格式文档文本（仅标题和内容）。

    用于没有作者和分类信息时的简化场景。

    Args:
        thread_name: 帖子标题
        content: 帖子正文内容

    Returns:
        简单格式的文档文本字符串
    """
    return f"标题: {thread_name}\n\n内容:\n{content}"
