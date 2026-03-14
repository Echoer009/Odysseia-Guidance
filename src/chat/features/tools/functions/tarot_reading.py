# -*- coding: utf-8 -*-
"""
塔罗占卜工具 - 为用户执行塔罗牌占卜
"""

import io
import logging
from typing import Dict, Any, Literal

import discord
from pydantic import BaseModel, Field

from src.chat.features.tarot.services import tarot_service
from src.chat.utils.database import chat_db_manager
from src.chat.features.tarot.config.tarot_config import TarotConfig
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


class TarotReadingParams(BaseModel):
    """塔罗占卜参数"""

    question: str = Field(
        default="关于我最近的整体运势",
        description="用户提出的具体问题。若没有提供，默认为整体运势。",
    )
    spread_type: Literal["three_card", "single_card"] = Field(
        default="three_card",
        description="牌阵类型: 'three_card'(三张牌) 或 'single_card'(单张牌)。",
    )


@tool_metadata(
    name="塔罗占卜",
    description="抽张塔罗牌看看运势，可问问题或看整体运势",
    emoji="🃏",
    category="娱乐",
)
async def tarot_reading(
    params: TarotReadingParams,
    **kwargs,
) -> Dict[str, Any]:
    """
    为用户执行塔罗牌占卜。当用户请求占卜、算命或想看运势时调用。
    工具会生成并发送牌阵图片，返回牌面信息供解读。
    """
    # 从 Pydantic 模型中提取参数
    question = params.question
    spread_type = params.spread_type

    log.info(
        f"--- [工具执行]: tarot_reading, 参数: question='{question}', spread_type='{spread_type}' ---"
    )

    channel = kwargs.get("channel")
    if not channel:
        log.error("无法执行塔罗牌占卜：缺少 'channel' 对象。")
        return {
            "error": "Cannot perform tarot reading without a valid channel to send the image to."
        }

    if (
        TarotConfig.RESTRICTED_GUILD_ID
        and channel.guild
        and channel.guild.id == TarotConfig.RESTRICTED_GUILD_ID
    ):
        if channel.id != TarotConfig.ALLOWED_CHANNEL_ID:
            log.warning(
                f"塔罗牌工具在受限服务器 {TarotConfig.RESTRICTED_GUILD_ID} 的不允许的频道 {channel.id} 中被调用。"
            )
            return {
                "error": f"在这里占卜会刷屏啦，星辰与命运的指引只在特定的圣地展现。请移步至https://discord.com/channels/{TarotConfig.RESTRICTED_GUILD_ID}/{TarotConfig.ALLOWED_CHANNEL_ID}，再次寻求塔罗的启示吧。"
            }

    try:
        await chat_db_manager.increment_tarot_reading_count()
        image_data, cards = await tarot_service.perform_reading(question, spread_type)

        if image_data and cards:
            log.info(f"成功生成塔罗牌图片，准备发送到频道 {channel.id}。")

            image_file = discord.File(
                io.BytesIO(image_data), filename="tarot_reading.png"
            )
            await channel.send(file=image_file)

            log.info("塔罗牌图片发送成功。")

            card_details = []
            for card in cards:
                card_details.append(
                    {
                        "name": card["name"],
                        "orientation": card["orientation"],
                        "meaning_up": card["meaning_up"],
                        "meaning_rev": card["meaning_rev"],
                    }
                )

            return {
                "status": "image_sent_successfully",
                "question": question,
                "cards": card_details,
            }
        else:
            log.error("塔罗牌占卜失败：未能生成图片或抽到牌。")
            await channel.send("抱歉，塔罗牌占卜出了一点小问题，无法生成牌阵图片。")
            return {"error": "Failed to generate tarot image or draw cards."}

    except Exception as e:
        log.error("执行塔罗牌占卜时发生未知错误。", exc_info=True)
        await channel.send("抱歉，塔罗牌占卜时遇到了一个意想不到的错误。")
        return {"error": f"An unexpected error occurred: {str(e)}"}
