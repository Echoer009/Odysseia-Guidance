# -*- coding: utf-8 -*-

import re


class RegexService:
    """
    一个专门用于处理和清理文本中特定模式的的服务。
    """

    def clean_ai_output(self, text: str) -> str:
        """
        清理AI模型的输出文本。
        - 移除 () 和 [] 及其内部内容。
        - 移除全角/半角括号。
        """
        if not isinstance(text, str):
            return ""

        # 匹配 (), （）
        text = re.sub(r"[\(（][^)）]*[\)）]:?\s*", "", text)
        # 匹配 [], 【】
        text = re.sub(r"[\[【][^\]】]*[\]】]:?\s*", "", text)
        return text.strip()

    def clean_user_input(self, text: str) -> str:
        """
        清理用户的输入文本，移除可能用于Prompt Injection的各种标记和格式。
        - 移除各种括号及其内部内容: (), [], {}, <>
        - 移除Markdown格式: 代码块, 引用, 标题
        """
        if not isinstance(text, str):
            return ""

        # 移除 (), （）, [], 【】, {}, 《》 及其内部内容
        text = re.sub(r"[\(（][^)）]*[\)）]:?\s*", "", text)
        text = re.sub(r"[\[【][^\]】]*[\]】]:?\s*", "", text)
        text = re.sub(r"\{[^\}]*\}", "", text)
        text = re.sub(r"《[^》]*》", "", text)

        # 移除所有剩余的XML/HTML标签
        # 此时真实的Discord表情应该已经被移除了，所以我们可以安全地移除所有 <...> 格式的文本
        # 修改正则表达式，以避免移除 Discord 的提及（用户, 角色, 频道）
        # 这个正则表达式会匹配所有 <...> 结构，但会排除 <@...> <@&...> <@!...> 和 <#...>
        text = re.sub(r"<(?![@#&!])([^>]+)>", "", text)

        # 移除Markdown代码块 (```...``` 和 `...`)
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"`[^`]*`", "", text)

        # 移除Markdown引用和标题
        text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)

        return text.strip()


# 全局实例
regex_service = RegexService()
