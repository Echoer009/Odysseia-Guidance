# -*- coding: utf-8 -*-

import json
import ast
import logging
from typing import Mapping, Any, Dict

log = logging.getLogger(__name__)


def _parse_raw_profile_data(raw_data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    从原始数据库行中解析出个人档案的核心字段。
    这个逻辑是从 EditCommunityMemberModal.__init__ 中提取和优化的。
    """
    full_text = raw_data.get("full_text", "")
    source_metadata = raw_data.get("source_metadata", {})

    # 优先从 full_text 解析
    if full_text:
        # 尝试解析格式化的 "键: 值" 文本
        if "名称:" in full_text and "Discord ID:" in full_text:
            lines = full_text.strip().split("\n")
            temp_data = {}
            for line in lines:
                if ": " in line:
                    key, value = line.split(": ", 1)
                    key_map = {
                        "名称": "name",
                        "Discord ID": "discord_id",
                        "性格特点": "personality",
                        "背景信息": "background",
                        "喜好偏好": "preferences",
                    }
                    field_name = key_map.get(key.strip())
                    if field_name:
                        temp_data[field_name] = value.strip()
            if temp_data.get("name"):
                return temp_data

        # 尝试解析 JSON
        try:
            cleaned_full_text = full_text.strip()
            if cleaned_full_text.startswith("{"):
                data = json.loads(cleaned_full_text)
                if isinstance(data, dict) and data.get("name"):
                    return data
        except (json.JSONDecodeError, TypeError):
            pass

    # 如果 full_text 失败，从 source_metadata 解析
    if source_metadata:
        try:
            metadata = source_metadata
            if isinstance(metadata, str):
                metadata = ast.literal_eval(metadata)

            if isinstance(metadata, dict):
                # 检查 content_json
                if "content_json" in metadata and metadata["content_json"]:
                    content_json_str = metadata["content_json"]
                    if isinstance(content_json_str, str):
                        data = json.loads(content_json_str)
                    else:
                        data = content_json_str
                    if data.get("name"):
                        return data
                # 检查元数据本身
                if metadata.get("name"):
                    return metadata
        except (json.JSONDecodeError, TypeError, ValueError, SyntaxError) as e:
            log.warning(f"无法从 source_metadata 解析档案数据: {e}")

    # 最后的保障：从顶层字段获取
    return {
        "name": raw_data.get("title", ""),
        "discord_id": raw_data.get("discord_id", ""),
        "personality": "",
        "background": "",
        "preferences": "",
    }


def format_member_profile(raw_data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    接收一个原始的数据库行，返回一个包含格式化好的
    full_text 和 source_metadata 的字典。
    这个逻辑是从 EditCommunityMemberModal.on_submit 中提取的。
    """
    # 1. 解析出核心数据
    parsed_data = _parse_raw_profile_data(raw_data)

    name = parsed_data.get("name", "").strip()
    discord_id = str(parsed_data.get("discord_id", "")).strip()
    personality = parsed_data.get("personality", "").strip()
    background = parsed_data.get("background", "").strip()
    preferences = parsed_data.get("preferences", "").strip()

    # 2. 重建干净的 full_text
    formatted_full_text = f"""名称: {name}
Discord ID: {discord_id}
性格特点: {personality}
背景信息: {background}
喜好偏好: {preferences}""".strip()

    # 3. 重建干净的 source_metadata (作为字典)
    formatted_source_metadata = {
        "name": name,
        "discord_id": discord_id,
        "personality": personality,
        "background": background,
        "preferences": preferences,
    }

    return {
        "full_text": formatted_full_text,
        "source_metadata": formatted_source_metadata,
    }
