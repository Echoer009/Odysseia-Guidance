# -*- coding: utf-8 -*-

import re


class RegexService:
    """
    一个专门用于处理和清理文本中特定模式的的服务。
    """

    def clean_channel_name(self, name: str) -> str:
        """
        清洗频道名称，移除 emoji 和常见的装饰性符号，并应用特定的重命名规则。
        """
        if not isinstance(name, str):
            return name

        # 特定的重命名规则
        special_rules = {
            "🪓︱预设ᴾʳᵉˢᵉᵗ＆破限ᴶᴮ": "预设",
            "💟︱教程分享": "教程",
            "👑｜酒馆美化": "美化",
            "🔧︱酒馆插件": "插件",
        }

        # 1. 优先应用特定的重命名规则
        # 为了精确匹配，先对输入名称进行初步的通用清理
        temp_cleaned_name = re.sub(r"\s+", " ", name).strip()
        for original, new_name in special_rules.items():
            # 也对规则中的键进行同样的清理，以防空格不一致
            cleaned_original = re.sub(r"\s+", " ", original).strip()
            if cleaned_original in temp_cleaned_name:
                return new_name

        # 2. 如果没有匹配到特定规则，则执行通用清理
        # 移除 emoji
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "\U00002600-\U000027bf"  # Miscellaneous Symbols
            "\U0001f900-\U0001f9ff"  # Supplemental Symbols
            "]+",
            flags=re.UNICODE,
        )
        cleaned_name = emoji_pattern.sub("", name)

        # 移除常见的装饰性字符
        cleaned_name = re.sub(r"[|｜︱🔨🪓👑💟🔧丨]", "", cleaned_name)

        # 移除前后及中间多余的空格
        cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()

        return cleaned_name

    def clean_ai_output(self, text: str) -> str:
        """
        清理AI模型的输出文本。
        - 移除 () 和 [] 及其内部内容，但保留 Markdown 链接。
        - 移除全角/半角括号。
        """
        if not isinstance(text, str):
            return ""

        # 移除模型输出中可能包含的各种思考过程标签和内容
        think_pattern = re.compile(
            r"<(思考|think|thinking|thought|scratchpad|reasoning|rationale)>.*?</\1>\s*",
            re.DOTALL | re.IGNORECASE,
        )
        text = think_pattern.sub("", text)

        # 替换 1011 为 [数据删除]
        text = re.sub(r"1011", "[数据删除]", text)

        return text.strip()

    def clean_user_input(self, text: str) -> str:
        """
        清理用户的输入文本，移除可能用于Prompt Injection的各种标记和格式。
        - 移除各种括号及其内部内容: (), [], {}, <>
        - 移除Markdown格式: 代码块, 引用, 标题
        """
        if not isinstance(text, str):
            return ""

        # 移除 (), （）, [], 【】, {} 及其内部内容
        text = re.sub(r"[\(（][^)）]*[\)）]:?\s*", "", text)
        text = re.sub(r"[\[【][^\]】]*[\]】]:?\s*", "", text)
        text = re.sub(r"\{[^\}]*\}", "", text)

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
