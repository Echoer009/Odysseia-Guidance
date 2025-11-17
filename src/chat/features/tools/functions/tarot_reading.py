import logging
from typing import Dict, Any
import io
import discord

from src.chat.features.tarot.services import tarot_service
from src.chat.features.tarot.config.tarot_config import TarotConfig

log = logging.getLogger(__name__)


async def tarot_reading(
    question: str = "关于我最近的整体运势", spread_type: str = "three_card", **kwargs
) -> Dict[str, Any]:
    """
    为用户执行一次塔罗牌占卜。
    当用户请求占卜、算命或想看未来运势时调用此工具。工具会生成并自动发送一张包含牌阵的图片，然后返回牌面的信息供你解读。

    Args:
        question (str): 用户提出的具体问题。如果用户没有提供，则默认为“关于我最近的整体运势”。
        spread_type (str): 使用的牌阵类型。默认为 'three_card'（三张牌）。也可以是 'single_card'（单张牌）。

    Returns:
        一个字典，其中包含抽到的牌的详细信息，供你进行解读。
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

    # 检查是否在特定服务器的特定频道中使用
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
        log.error("执行塔罗牌占卜时发生未知错误。", exc_info=True)
        await channel.send("抱歉，塔罗牌占卜时遇到了一个意想不到的错误。")
        return {"error": f"An unexpected error occurred: {str(e)}"}
