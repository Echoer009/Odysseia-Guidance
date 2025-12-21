import re
import random
from src.chat.config.prompts import SYSTEM_PROMPT
from src.chat.config.emoji_config import EMOJI_MAPPINGS, FACTION_EMOJI_MAPPINGS
from src.chat.services.event_service import event_service
import logging

log = logging.getLogger(__name__)


def replace_emojis(text: str) -> str:
    """
    根据 emoji_config.py 中的映射规则，
    将文本中的自定义表情占位符（如 <微笑>）替换为对应的 Discord 自定义表情（如 <:xianhua:12345>）。
    此函数现在会根据当前活动和派系动态选择表情包。
    """
    faction_info = event_service.get_selected_faction_info()
    processed_text = text

    # 首先尝试使用派系专属表情包
    if faction_info:
        event_id = faction_info.get("event_id")
        faction_id = faction_info.get("faction_id")

        if event_id and faction_id:
            faction_map = FACTION_EMOJI_MAPPINGS.get(event_id, {}).get(faction_id)
            if faction_map:
                log.info(
                    f"prompt_utils: 正在为事件 '{event_id}' 的派系 '{faction_id}' 应用专属表情包。"
                )
                for pattern, replacement_list in faction_map:
                    if replacement_list:
                        # 使用 lambda 函数为每个匹配项随机选择一个替换
                        processed_text = pattern.sub(
                            lambda m: random.choice(replacement_list), processed_text
                        )

    # 然后，对剩余的占位符（或所有占位符，如果没有派系包）使用默认表情包
    for pattern, replacement_list in EMOJI_MAPPINGS:
        if replacement_list:
            processed_text = pattern.sub(
                lambda m: random.choice(replacement_list), processed_text
            )

    return processed_text


def extract_persona_prompt(system_prompt: str) -> str:
    """
    从 SYSTEM_PROMPT 中提取 <character> 标签内的全部内容，
    用于构建 /投喂 命令的提示词。
    """
    # 使用正则表达式提取 <character> 标签及其所有内容
    match = re.search(r"<character>.*?</character>", system_prompt, re.DOTALL)

    if match:
        # 如果找到匹配项，则返回整个 <character>...</character> 块
        return match.group(0)
    else:
        # 如果没有找到，返回一个空字符串以避免意外注入规则
        return ""


def get_core_persona() -> str:
    """
    为暖贴功能，从 SYSTEM_PROMPT 中提取特定的、精简的人设信息。
    此函数现在与 get_thread_commentor_persona 功能相同。
    """
    return get_thread_commentor_persona()


def get_thread_commentor_persona() -> str:
    """
    为暖贴功能，从 SYSTEM_PROMPT 中提取特定的、精简的人设信息。
    使用独立的标签来确保提取的准确性。
    包括:
    - <core_identity>
    - <markdown_guidelines>
    - <emoji_guidelines>
    """
    # 提取 <core_identity>
    core_identity_match = re.search(
        r"<core_identity>.*?</core_identity>", SYSTEM_PROMPT, re.DOTALL
    )
    core_identity = core_identity_match.group(0) if core_identity_match else ""

    # 提取 <markdown_guidelines>
    markdown_guidelines_match = re.search(
        r"<markdown_guidelines>.*?</markdown_guidelines>", SYSTEM_PROMPT, re.DOTALL
    )
    markdown_guidelines = (
        markdown_guidelines_match.group(0) if markdown_guidelines_match else ""
    )

    # 提取 <emoji_guidelines>
    emoji_guidelines_match = re.search(
        r"<emoji_guidelines>.*?</emoji_guidelines>", SYSTEM_PROMPT, re.DOTALL
    )
    emoji_guidelines = emoji_guidelines_match.group(0) if emoji_guidelines_match else ""

    # 按照要求的格式拼接
    parts = [core_identity, markdown_guidelines, emoji_guidelines]

    # 过滤掉空字符串并用换行符连接
    final_persona = "\n\n".join(part for part in parts if part)

    return final_persona
