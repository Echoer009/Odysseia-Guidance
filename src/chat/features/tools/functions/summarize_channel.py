# -*- coding: utf-8 -*-
"""
频道总结工具 - 获取并总结频道消息历史
"""

import io
import logging
import os
import re
from datetime import datetime
from typing import Optional

import discord
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


class SummarizeChannelParams(BaseModel):
    """频道总结参数"""

    limit: int = Field(
        default=200,
        description="要获取的消息数量，默认200条。",
    )
    start_date: Optional[str] = Field(
        None,
        description="开始日期 (格式: YYYY-MM-DD)",
    )
    end_date: Optional[str] = Field(
        None,
        description="结束日期 (格式: YYYY-MM-DD)",
    )


@tool_metadata(
    name="总结",
    description="获取频道消息历史用于总结，可指定消息数量和时间范围",
    emoji="📝",
    category="总结",
)
async def summarize_channel(
    params: SummarizeChannelParams,
    **kwargs,
) -> str:
    """
    获取当前频道的消息历史。仅在用户明确要求"总结"时使用。
    返回的消息格式为"作者(时间): 内容"。
    """
    channel = kwargs.get("channel")
    if not channel or not isinstance(channel, discord.abc.Messageable):
        return "错误：无法在当前上下文中找到有效的频道。"

    # params 已经由 tool_service 自动转换为 SummarizeChannelParams
    limit = min(params.limit, 500)

    after = None
    if params.start_date:
        try:
            after = datetime.strptime(params.start_date, "%Y-%m-%d")
        except ValueError:
            return "错误: `start_date` 格式不正确，请使用 YYYY-MM-DD 格式。"

    before = None
    if params.end_date:
        try:
            before = datetime.strptime(params.end_date, "%Y-%m-%d")
        except ValueError:
            return "错误: `end_date` 格式不正确，请使用 YYYY-MM-DD 格式。"

    channel_id = getattr(channel, "id", "未知")
    log.info(
        f"工具 'summarize_channel' 被调用，在频道 {channel_id} 中获取 {limit} 条消息"
    )

    try:
        messages = []
        async for message in channel.history(limit=limit, before=before, after=after):
            if message.author.bot or not message.content:
                continue
            local_time = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            messages.append(
                f"{message.author.display_name}({local_time}): {message.content}"
            )

        messages.reverse()

        if not messages:
            return "在指定范围内没有找到消息。"

        return "\n".join(messages)

    except discord.Forbidden:
        log.error(f"机器人缺少访问频道 {channel_id} 历史记录的权限。")
        return "错误：我没有权限查看这个频道的历史记录。"
    except Exception as e:
        log.error(f"处理频道 {channel_id} 的消息时发生未知错误: {e}")
        return f"错误：处理消息时发生未知错误: {e}"


def text_to_summary_image(
    text: str, title: str = "类脑娘的总结时间到!"
) -> Optional[bytes]:
    """
    将文本转换为一张自适应高度的长图，能正确处理换行和避让右上角的Logo。
    """
    LOGO_PATH = "src/chat/assets/logo.png"
    FONT_PATH = "src/chat/assets/font.TTF"
    IMG_WIDTH = 1200
    MARGIN = 60
    LINE_SPACING = 15
    TITLE_FONT_SIZE = 48
    BODY_FONT_SIZE = 32
    BG_COLOR = (43, 45, 49, 255)
    TEXT_COLOR = (220, 221, 222, 255)
    LOGO_MAX_SIZE = (250, 250)

    try:
        try:
            title_font = ImageFont.truetype(FONT_PATH, size=TITLE_FONT_SIZE)
            body_font = ImageFont.truetype(FONT_PATH, size=BODY_FONT_SIZE)
        except IOError:
            log.error(f"字体文件在 '{FONT_PATH}' 未找到！无法生成图片。")
            return None

        logo_img = None
        logo_w, logo_h = 0, 0
        if os.path.exists(LOGO_PATH):
            logo_img = Image.open(LOGO_PATH).convert("RGBA")
            logo_img.thumbnail(LOGO_MAX_SIZE, Image.Resampling.LANCZOS)
            logo_w, logo_h = logo_img.size
        else:
            log.warning(f"Logo 文件未找到: {LOGO_PATH}")

        emoji_pattern = r"<a?:.+?:\d+>"
        clean_text = re.sub(emoji_pattern, "", text).strip()

        lines = []
        current_y = float(MARGIN)

        title_bbox = title_font.getbbox(title)
        title_height = title_bbox[3] - title_bbox[1]
        lines.append(
            {"text": title, "y": current_y, "font": title_font, "color": TEXT_COLOR}
        )
        current_y += title_height + 30

        body_bbox = body_font.getbbox("A")
        line_height = (body_bbox[3] - body_bbox[1]) + LINE_SPACING

        full_width = IMG_WIDTH - 2 * MARGIN
        short_width = IMG_WIDTH - 2 * MARGIN - logo_w - int(MARGIN / 2)
        logo_area_y_end = MARGIN + logo_h

        paragraphs = clean_text.split("\n")
        for para in paragraphs:
            if not para.strip():
                current_y += line_height
                continue

            current_line = ""
            for char in para:
                max_width_for_line = (
                    short_width
                    if current_y < logo_area_y_end and logo_img
                    else full_width
                )

                line_if_added = f"{current_line}{char}"
                if body_font.getlength(line_if_added) <= max_width_for_line:
                    current_line = line_if_added
                else:
                    lines.append(
                        {
                            "text": current_line,
                            "y": current_y,
                            "font": body_font,
                            "color": TEXT_COLOR,
                        }
                    )
                    current_y += line_height
                    current_line = char

            if current_line:
                lines.append(
                    {
                        "text": current_line,
                        "y": current_y,
                        "font": body_font,
                        "color": TEXT_COLOR,
                    }
                )
                current_y += line_height

        total_height = int(current_y - line_height + body_bbox[3] + MARGIN)

        image = Image.new("RGBA", (IMG_WIDTH, total_height), BG_COLOR)
        draw = ImageDraw.Draw(image)

        if logo_img:
            logo_x = IMG_WIDTH - logo_w - MARGIN
            logo_y = MARGIN
            image.paste(logo_img, (logo_x, logo_y), logo_img)

        for line_info in lines:
            draw.text(
                (MARGIN, line_info["y"]),
                line_info["text"],
                font=line_info["font"],
                fill=line_info["color"],
            )

        output_buffer = io.BytesIO()
        image.save(output_buffer, format="PNG")
        image_bytes = output_buffer.getvalue()

        log.info(
            f"成功创建长图，尺寸: {IMG_WIDTH}x{total_height}，大小: {len(image_bytes) / 1024:.2f} KB"
        )
        return image_bytes

    except Exception as e:
        log.error(f"创建文本转图片时发生严重错误: {e}", exc_info=True)
        return None
