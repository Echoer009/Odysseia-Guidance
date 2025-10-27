import re
from typing import Dict, Any


def parse_channel_messages(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    templates = {}
    template_pattern = re.compile(
        r"###\s*.*?`((?:channel|forum|thread)\(\d+\))`\s*(.+?)(?=\n###|\Z)", re.S
    )

    def _parse_single_message_block(msg_content):
        if not msg_content:
            return None
        msg_data = {}

        def extract(pattern, text):
            match = re.search(pattern, text, re.S)
            return match.group(1).strip() if match else None

        msg_data["title"] = extract(r"\*\s*\*Embed 标题:\*\*\s*`(.+?)`", msg_content)
        desc_raw = extract(r"\*\s*\*Embed 描述:\*\*\s*(.+?)(?=\n\s*\*|\Z)", msg_content)
        if desc_raw:
            cleaned = (
                desc_raw.strip().replace("> ", "").replace(">", "").replace("\\n", "\n")
            )
            msg_data["description"] = cleaned
        msg_data["image_url"] = extract(
            r"\*\s*\*Embed 大图 URL:\*\*\s*`(.+?)`", msg_content
        )
        msg_data["thumbnail_url"] = extract(
            r"\*\s*\*Embed 缩略图 URL:\*\*\s*`(.+?)`", msg_content
        )
        msg_data["footer_text"] = extract(
            r"\*\s*\*Embed 页脚:\*\*\s*`(.+?)`", msg_content
        )

        return {k: v for k, v in msg_data.items() if v}

    for match in template_pattern.finditer(content):
        template_name, block_content = match.groups()
        parsed_data = {"permanent_data": [], "temporary_data": []}

        perm_match = re.search(
            r"\*\s*\*\*永久消息面板\s*\(.+?\)\*\*(.+?)(?=\n\s*\*\s*\*\*临时消息|\Z)",
            block_content,
            re.S,
        )
        if perm_match:
            perm_message = _parse_single_message_block(perm_match.group(1))
            if perm_message:
                parsed_data["permanent_data"].append(perm_message)

        temp_list_match = re.search(
            r"\*\s*\*\*临时消息(?:列表)?\s*\(.+?\)\*\*(.+)", block_content, re.S
        )
        if temp_list_match:
            message_blocks = re.split(r"\n\s*\*\s*\-", temp_list_match.group(1))
            for block in message_blocks:
                if block.strip():
                    cleaned_block = re.sub(r"^\s*\*\s*", "", block).strip()
                    if cleaned_block:
                        temp_message = _parse_single_message_block(cleaned_block)
                        if temp_message:
                            parsed_data["temporary_data"].append(temp_message)

        if parsed_data["permanent_data"] or parsed_data["temporary_data"]:
            templates[template_name] = parsed_data

    return templates
