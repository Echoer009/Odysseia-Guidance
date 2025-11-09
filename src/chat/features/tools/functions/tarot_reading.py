import logging
from typing import Dict, Any
import io
import discord

from src.chat.features.tarot.services import tarot_service

log = logging.getLogger(__name__)


async def tarot_reading(
    question: str = "关于我最近的整体运势", spread_type: str = "three_card", **kwargs
) -> Dict[str, Any]:
    """
    为用户执行塔罗牌占卜，并发送一张包含牌阵的图片。

    Args:
        question (str): 用户提出的具体问题。如果用户没有提供，则默认为“关于我最近的整体运势”。这个问题将帮助AI更好地解读牌意。
        spread_type (str): 使用的牌阵类型。默认为 'three_card'（三张牌）。也可以是 'single_card'（单张牌）。

    Returns:
        一个字典，其中包含抽到的牌的详细信息，供AI进行解读。如果成功，AI会说图片已发送；如果失败，则返回错误信息。
    """
    log.info(
        f"--- [工具执行]: tarot_reading, 参数: question='{question}', spread_type='{spread_type}' ---"
    )

    channel = kwargs.get("channel")
    if not channel:
        log.error("无法执行塔罗牌占卜：缺少 'channel' 对象。")
        return {
            "error": "Cannot perform tarot reading without a valid channel to send the image to."
        }

    try:
        image_data, cards = await tarot_service.perform_reading(question, spread_type)

        if image_data and cards:
            log.info(f"成功生成塔罗牌图片，准备发送到频道 {channel.id}。")

            # 将图片数据转换为 discord.File 并发送
            image_file = discord.File(
                io.BytesIO(image_data), filename="tarot_reading.png"
            )
            await channel.send(file=image_file)

            log.info("塔罗牌图片发送成功。")

            # 准备返回给 AI 的数据
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
        log.error(f"执行塔罗牌占卜时发生未知错误。", exc_info=True)
        await channel.send("抱歉，塔罗牌占卜时遇到了一个意想不到的错误。")
        return {"error": f"An unexpected error occurred: {str(e)}"}
