# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import re
import json
from collections import defaultdict
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 将 src 目录添加到 Python 路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from guidance.utils.database import guidance_db_manager as db_manager
from config import GUILD_ID


def parse_markdown_templates(file_path):
    """
    解析 markdown 文件，提取所有消息模板。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    templates = {}
    template_pattern = re.compile(
        r"###\s*.*?`((?:channel|forum|thread)\(\d+\))`\s*\)(.+?)(?=\n###|\Z)", re.S
    )

    def _parse_single_message_block(msg_content):
        if not msg_content:
            return None
        msg_data = {}

        def extract_field(pattern, text):
            match = re.search(pattern, text, re.S)
            if match:
                return match.group(1).strip()
            return None

        msg_data["title"] = extract_field(
            r"\s*\*\s*\*Embed 标题:\*\*\s*`(.+?)`", msg_content
        )

        description_raw = extract_field(
            r"\s*\*\s*\*Embed 描述:\*\*\s*(.+?)(?=\n\s*\*|\Z)", msg_content
        )
        if description_raw:
            # 移除 markdown 引用符号
            cleaned_description = (
                description_raw.strip().replace("> ", "").replace(">", "")
            )
            # 处理转义的换行符
            cleaned_description = cleaned_description.replace("\\n", "\n")
            msg_data["description"] = cleaned_description

        msg_data["image_url"] = extract_field(
            r"\s*\*\s*\*Embed 大图 URL:\*\*\s*`(.+?)`", msg_content
        )
        msg_data["thumbnail_url"] = extract_field(
            r"\s*\*\s*\*Embed 缩略图 URL:\*\*\s*`(.+?)`", msg_content
        )
        msg_data["footer_text"] = extract_field(
            r"\s*\*\s*\*Embed 页脚:\*\*\s*`(.+?)`", msg_content
        )

        # 移除值为 None 或空字符串的键
        msg_data = {k: v for k, v in msg_data.items() if v is not None and v != ""}

        return msg_data if msg_data else None

    for match in template_pattern.finditer(content):
        template_name, block_content = match.groups()

        parsed_data = {"permanent_data": [], "temporary_data": []}

        # 提取永久消息内容
        perm_match = re.search(
            r"\*\s*\*\*永久消息面板\s*\(.+?\)\*\*(.+?)(?=\n\s*\*\s*\*\*临时消息|\Z)",
            block_content,
            re.S,
        )
        if perm_match:
            perm_content = perm_match.group(1)
            perm_message = _parse_single_message_block(perm_content)
            if perm_message:
                parsed_data["permanent_data"].append(perm_message)

        # 提取临时消息列表内容 - 同时匹配"临时消息列表"和"临时消息"
        temp_list_match = re.search(
            r"\*\s*\*\*临时消息(?:列表)?\s*\(.+?\)\*\*(.+)", block_content, re.S
        )
        if temp_list_match:
            temp_list_content = temp_list_match.group(1)
            # 寻找所有以 '*' 开头的消息块（每个消息块以 "*   -" 开头）
            message_blocks = re.split(r"\n\s*\*\s*\-", temp_list_content)
            for block in message_blocks:
                if block.strip():
                    # 清理每个块开头的列表标记和缩进
                    cleaned_block = re.sub(r"^\s*\*\s*", "", block).strip()
                    if cleaned_block:
                        temp_message = _parse_single_message_block(cleaned_block)
                        if temp_message:
                            parsed_data["temporary_data"].append(temp_message)

        if parsed_data["permanent_data"] or parsed_data["temporary_data"]:
            templates[template_name] = parsed_data

    return templates


async def main():
    """
    主函数，解析 channel_templates.md 并根据模板名称中的 ID 将数据直接存入数据库。
    """
    if not GUILD_ID:
        print("错误：请在 .env 文件中设置 GUILD_ID")
        return

    guild_id = int(GUILD_ID)

    print("正在解析 channel_templates.md 文件...")
    try:
        script_dir = os.path.dirname(__file__)
        templates_file = os.path.join(script_dir, "..", "docs", "channel_message.md")
        templates_data = parse_markdown_templates(templates_file)
        print(f"✅ 解析成功，找到 {len(templates_data)} 个模板定义。")
    except Exception as e:
        print(f"❌ 解析 markdown 文件时出错: {e}")
        return

    # 按 channel_id/thread_id 对模板数据进行分组
    configs_to_set = defaultdict(lambda: {"permanent_data": {}, "temporary_data": []})

    # 正则表达式，用于从模板名称中提取类型和ID
    # 正则表达式，用于从模板名称中提取类型和ID (例如 'channel_permanent_ID_HERE')
    name_pattern = re.compile(r"(channel|forum|thread)\((\d+)\)")

    for template_name, data in templates_data.items():
        # 将ID占位符替换为实际的数字ID
        if "ID_HERE" in template_name:
            print(f"⚠️  跳过未填写ID的模板: '{template_name}'")
            continue

        match = name_pattern.match(template_name)
        if not match:
            print(f"⚠️  跳过格式不匹配的模板: '{template_name}' (请确保ID已正确填写)")
            continue

        loc_type, loc_id_str = match.groups()
        loc_id = int(loc_id_str)

        # data 是一个包含 'permanent_data' 和 'temporary_data' 的字典
        if "permanent_data" in data and data["permanent_data"]:
            configs_to_set[loc_id]["permanent_data"] = data["permanent_data"][0]

        if "temporary_data" in data and data["temporary_data"]:
            configs_to_set[loc_id]["temporary_data"].extend(data["temporary_data"])

    if not configs_to_set:
        print("ℹ️  没有找到符合命名约定的模板来更新数据库。")
        return

    print(f"\n准备将 {len(configs_to_set)} 个地点的配置写入数据库...")

    for location_id, config_data in configs_to_set.items():
        try:
            # 获取已有的数据，以免完全覆盖
            # existing_config = await db_manager.get_channel_message(location_id) or {}

            # 如果模板中定义了新数据，则使用新数据，否则保留旧数据
            # final_permanent_data = config_data["permanent_data"] or existing_config.get("permanent_message_data", {})
            # final_temporary_data = config_data["temporary_data"] or existing_config.get("temporary_message_data", [])

            # 修改为完全覆盖逻辑：直接使用模板数据，不保留任何旧数据
            final_permanent_data = config_data["permanent_data"]
            final_temporary_data = config_data["temporary_data"]

            print(f"  - 正在设置地点 ID: {location_id}...")
            await db_manager.set_channel_message(
                guild_id=guild_id,
                channel_id=location_id,
                permanent_data=final_permanent_data,
                temporary_data=final_temporary_data,
            )
            print(
                f"    ✅ 成功。永久消息: {'已设置' if final_permanent_data else '未设置'}, 临时消息: {len(final_temporary_data)} 条。"
            )
        except Exception as e:
            print(f"    ❌ 处理地点 ID '{location_id}' 时发生错误: {e}")

    print("\n所有频道模板数据导入完成。")


if __name__ == "__main__":
    asyncio.run(main())
