import discord
import json
import io
import re
import time
from discord import app_commands
from discord.ext import commands

from src.chat.features.affection.service.affection_service import AffectionService
from src.chat.features.affection.service.feeding_service import feeding_service
from src.chat.features.odysseia_coin.service.coin_service import CoinService
from src.chat.services.ai.service import ai_service
from src.chat.services.ai.providers.base import GenerationConfig
from src.chat.services.prompt_service import prompt_service
from src.chat.services.event_service import event_service
from src.chat.services.gpt_image_service import gpt_image_service
from src.chat.config.chat_config import (
    FEEDING_CONFIG,
    PROMPT_CONFIG,
    GEMINI_FEEDING_GEN_CONFIG,
)
from src.chat.config import chat_config
from src.chat.utils.prompt_utils import extract_persona_prompt, replace_emojis
from src.chat.utils.message_utils import truncate_text, DISCORD_EMBED_DESCRIPTION_LIMIT
from src.chat.utils.database import chat_db_manager
from src.config import DEVELOPER_USER_IDS
from src.chat.features.affection.utils.interaction_checks import (
    check_command_availability,
)
from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
import logging

logger = logging.getLogger(__name__)

_TAG_PATTERN = re.compile(r"`?\s*<([^>]*:[^>]*;[^>]*)>\s*`?", re.DOTALL)


def _parse_feeding_response(response_text: str):
    matches = _TAG_PATTERN.findall(response_text)
    if not matches:
        return None

    tag_content = matches[-1]

    start = response_text.rfind(f"<{tag_content}>")
    if start == -1:
        start = response_text.rfind(f"<{tag_content}")
    evaluation = response_text[:start].strip()

    fields = {}
    for pair in tag_content.split(";"):
        pair = pair.strip()
        if ":" in pair:
            key, value = pair.split(":", 1)
            fields[key.strip().lower()] = value.strip()

    try:
        affection_gain = int(fields.get("affection", "1"))
    except ValueError:
        affection_gain = 1
    try:
        coin_gain = int(fields.get("coins", "10"))
    except ValueError:
        coin_gain = 10

    is_food = fields.get("is_food", None)
    if is_food is None:
        coin_val = 0
        try:
            coin_val = int(fields.get("coins", "0"))
        except ValueError:
            pass
        is_food = coin_val >= 50
    else:
        is_food = is_food == "是"

    food_desc = fields.get("food_desc", "").strip()
    if food_desc in ("", "无"):
        food_desc = ""

    scene_desc = fields.get("scene_desc", "").strip()
    if scene_desc in ("", "无"):
        scene_desc = ""

    return {
        "evaluation": evaluation,
        "affection_gain": affection_gain,
        "coin_gain": coin_gain,
        "is_food": is_food,
        "food_desc": food_desc,
        "scene_desc": scene_desc,
    }


class FeedingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.affection_service = AffectionService()
        self.coin_service = CoinService()
        self.ai_service = ai_service
        self.feeding_service = feeding_service

    @app_commands.command(name="投喂", description="在吃饭?给类脑娘来一口怎么样")
    @app_commands.describe(image="拍一下你这顿饭是什么吧!")
    async def feed(self, interaction: discord.Interaction, image: discord.Attachment):
        is_allowed, error_message = await check_command_availability(
            interaction, "投喂"
        )
        if not is_allowed:
            await interaction.response.send_message(error_message, ephemeral=True)
            return

        user_id_int = interaction.user.id
        user_id_str = str(user_id_int)

        if user_id_int not in DEVELOPER_USER_IDS:
            can_feed, message = await self.feeding_service.can_feed(user_id_str)
            if not can_feed:
                await interaction.response.send_message(message, ephemeral=False)
                return

        await interaction.response.send_message("类脑娘正在嚼嚼嚼...", ephemeral=False)

        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.edit_original_response(
                content="欸？这个不能吃啦，给我看看真正的食物图片嘛！"
            )
            return

        response_text = ""
        try:
            image_bytes = await image.read()

            system_prompt = prompt_service.get_prompt("SYSTEM_PROMPT") or ""
            persona_part = extract_persona_prompt(system_prompt)
            base_prompt = PROMPT_CONFIG.get("feeding_prompt", "")
            prompt = f"{persona_part}\n\n{base_prompt}"

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "image_bytes": image_bytes,
                            "mime_type": image.content_type,
                        },
                    ],
                }
            ]

            config = GenerationConfig(
                temperature=GEMINI_FEEDING_GEN_CONFIG.get("temperature", 1.0),
                max_output_tokens=GEMINI_FEEDING_GEN_CONFIG.get(
                    "max_output_tokens", 8192
                ),
            )

            model_id = await chat_settings_service.get_current_ai_model()

            result = await ai_service.generate(
                messages=messages, config=config, model=model_id, enable_vision=True
            )
            response_text = result.content

            if not response_text:
                await interaction.edit_original_response(
                    content="抱歉，我有点累了，暂时无法评价呢。"
                )
                return

            parsed = _parse_feeding_response(response_text)

            if not parsed:
                logger.error(f"解析投喂评价失败。原始文本: '{response_text}'")
                evaluation = response_text
                affection_gain = 1
                coin_gain = 10
                is_food = False
                food_desc = ""
                scene_desc = ""
            else:
                evaluation = parsed["evaluation"]
                affection_gain = parsed["affection_gain"]
                coin_gain = parsed["coin_gain"]
                is_food = parsed["is_food"]
                food_desc = parsed["food_desc"]
                scene_desc = parsed["scene_desc"]

            logger.info(
                f"投喂解析结果: is_food={is_food}, food_desc='{food_desc}', "
                f"coins={coin_gain}, affection={affection_gain}, "
                f"原始回复前80字: '{response_text[:80]}'"
            )

            await self.affection_service.add_affection_points(
                user_id_int, affection_gain
            )

            if coin_gain > 0:
                await self.coin_service.add_coins(
                    user_id_int, coin_gain, reason="投喂奖励"
                )

            evaluation_with_emojis = replace_emojis(evaluation)

            system_message = ""
            if coin_gain > 0:
                system_message = f"> 你获得了 {coin_gain} 枚类脑币！"

            embed_description = evaluation_with_emojis
            if system_message:
                embed_description += f"\n\n{system_message}"
            embed_description = truncate_text(
                embed_description, DISCORD_EMBED_DESCRIPTION_LIMIT
            )

            embed = discord.Embed(
                description=embed_description,
                color=discord.Color.pink(),
            )

            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url,
            )

            file = discord.File(fp=io.BytesIO(image_bytes), filename=image.filename)
            embed.set_thumbnail(url=f"attachment://{image.filename}")

            is_unrestricted = (
                interaction.channel
                and interaction.channel.id in chat_config.UNRESTRICTED_CHANNEL_IDS
                or isinstance(interaction.channel, discord.Thread)
            )

            attachments = [file]

            generated_image_bytes = None
            if is_food and is_unrestricted and gpt_image_service.is_available:
                feeding_image_value = await chat_db_manager.get_global_setting(
                    "feeding_image_enabled"
                )
                feeding_image_enabled = (
                    feeding_image_value.lower() in ("true", "1", "yes", "on")
                    if feeding_image_value is not None
                    else True
                )
                if feeding_image_enabled:
                    gen_start = time.time()
                    try:
                        generated_image_bytes = await gpt_image_service.generate_feeding_image(
                            food_image_bytes=image_bytes,
                            food_mime_type=image.content_type,
                            food_description=food_desc,
                            scene_description=scene_desc,
                        )
                    except Exception as e:
                        gen_elapsed = time.time() - gen_start
                        logger.warning(
                            f"GPT Image 生图异常, 耗时 {gen_elapsed:.2f}s: {e}"
                        )
                    else:
                        gen_elapsed = time.time() - gen_start
                        if generated_image_bytes:
                            logger.info(
                                f"GPT Image 生图成功, 耗时 {gen_elapsed:.2f}s, "
                                f"大小 {len(generated_image_bytes)} bytes"
                            )

            if generated_image_bytes:
                gen_file = discord.File(
                    io.BytesIO(generated_image_bytes), filename="feeding_generated.png"
                )
                embed.set_image(url="attachment://feeding_generated.png")
                attachments.append(gen_file)
            elif is_unrestricted:
                sticker_url = None
                selected_faction_id = event_service.get_selected_faction()
                if selected_faction_id:
                    factions = event_service.get_event_factions()
                    if factions:
                        for faction in factions:
                            if faction.get("faction_id") == selected_faction_id:
                                sticker_url = faction.get("response_images", {}).get(
                                    "feeding", FEEDING_CONFIG.get("RESPONSE_IMAGE_URL")
                                )
                                break

                if not sticker_url:
                    sticker_url = FEEDING_CONFIG.get("RESPONSE_IMAGE_URL")

                if sticker_url:
                    embed.set_image(url=sticker_url)

            embed.set_footer(text="类脑娘对你的投喂做出回应...")

            await self.feeding_service.record_feeding(user_id_str)

            await interaction.edit_original_response(
                content=None, embed=embed, attachments=attachments
            )

        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from Gemini: {response_text}")
            await interaction.edit_original_response(
                content="呜... 我、我有点尝不出来味道... 你能等一下再喂我吗？"
            )
        except Exception as e:
            logger.error(f"Error processing feeding command: {e}")
            await interaction.edit_original_response(
                content="啊呀，不小心噎着了！等、等我一下，稍后再试试看！"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(FeedingCog(bot))
