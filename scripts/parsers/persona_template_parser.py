import re
from typing import Dict, Any


def parse_persona_templates(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    templates = {}
    template_pattern = re.compile(r"###\s*\d+\.\s*.*?`(.+?)`(.+?)(?=\n###|\Z)", re.S)

    for match in template_pattern.finditer(content):
        template_name, block_content = match.groups()
        messages = []

        message_blocks = re.split(r"\n\*\s*\*\*消息 \d+:\*\*", block_content)
        for msg_block in message_blocks:
            if not msg_block.strip():
                continue

            msg_data = {}
            title = re.search(r"\*\*Embed 标题:\*\*\s*`(.+?)`", msg_block, re.S)
            desc = re.search(
                r"\*\*Embed 描述:\*\*\s*(.+?)(?=\n\s*\*|\Z)", msg_block, re.S
            )
            thumb = re.search(r"\*\*Embed 缩略图 URL:\*\*\s*`(.+?)`", msg_block, re.S)
            footer = re.search(r"\*\*Embed 页脚:\*\*\s*`(.+?)`", msg_block, re.S)

            if title:
                msg_data["title"] = title.group(1).strip()
            if desc:
                msg_data["description"] = (
                    desc.group(1).strip().replace("> ", "").replace(">", "")
                )
            if thumb:
                msg_data["thumbnail_url"] = thumb.group(1).strip()
            if footer:
                msg_data["footer"] = footer.group(1).strip()

            if msg_data:
                messages.append(msg_data)

        if messages:
            templates[template_name] = messages

    return templates
