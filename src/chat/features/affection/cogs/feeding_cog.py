import discord
import json
import io
from discord import app_commands
from discord.ext import commands

from src.chat.utils.database import chat_db_manager
from src.chat.features.affection.service.affection_service import AffectionService
from src.chat.features.affection.service.feeding_service import feeding_service
from src.chat.features.odysseia_coin.service.coin_service import CoinService
from src.chat.services.gemini_service import gemini_service
from src.chat.services.prompt_service import prompt_service
from src.chat.config.chat_config import FEEDING_CONFIG, PROMPT_CONFIG
from src.chat.config import chat_config
from src.chat.utils.prompt_utils import extract_persona_prompt, replace_emojis
from src.config import DEVELOPER_USER_IDS
from src.chat.services.event_service import event_service
import logging

logger = logging.getLogger(__name__)


class FeedingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.affection_service = AffectionService()
        self.coin_service = CoinService()
        self.gemini_service = gemini_service  # 使用全局实例
        self.feeding_service = feeding_service

    @app_commands.command(name="投喂", description="在吃饭?给类脑娘来一口怎么样")
    @app_commands.describe(image="拍一下你这顿饭是什么吧!")
    async def feed(self, interaction: discord.Interaction, image: discord.Attachment):
        # --- 交互可用性检查 ---
        channel = interaction.channel
        # 0. 检查频道是否被禁言
        if channel and await chat_db_manager.is_channel_muted(channel.id):
            await interaction.response.send_message(
                "呜…我现在不能在这里说话啦…", ephemeral=True
            )
            return

        # 1. 检查是否在禁用的频道中
        if channel and channel.id in chat_config.DISABLED_INTERACTION_CHANNEL_IDS:
            await interaction.response.send_message(
                "嘘... 在这里我需要保持安静，我们去别的地方聊吧？", ephemeral=True
            )
            return

        # 2. 检查是否在置顶的帖子中
        if isinstance(channel, discord.Thread) and channel.flags.pinned:
            await interaction.response.send_message(
                "唔... 这个帖子被置顶了，一定是很重要的内容。我们不要在这里聊天，以免打扰到大家哦。",
                ephemeral=True,
            )
            return

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        # 检查用户是否为开发者，如果是，则绕过冷却时间检查
        if interaction.user.id not in DEVELOPER_USER_IDS:
            # 使用 FeedingService 检查是否可以投喂
            can_feed, message = await self.feeding_service.can_feed(user_id)
            if not can_feed:
                await interaction.response.send_message(message, ephemeral=False)
                return

        await interaction.response.send_message("类脑娘正在嚼嚼嚼...", ephemeral=False)

        if not image.content_type.startswith("image/"):
            await interaction.edit_original_response(
                content="欸？这个不能吃啦，给我看看真正的食物图片嘛！"
            )
            return

        try:
            image_bytes = await image.read()

            # 构建包含类脑娘人设的提示词
            persona_part = extract_persona_prompt(
                prompt_service.get_prompt("SYSTEM_PROMPT")
            )
            base_prompt = PROMPT_CONFIG.get("feeding_prompt", "")
            prompt = f"{persona_part}\n\n{base_prompt}"

            response_text = await self.gemini_service.generate_text_with_image(
                prompt=prompt, image_bytes=image_bytes, mime_type=image.content_type
            )

            if not response_text:
                await interaction.edit_original_response(
                    content="抱歉，我有点累了，暂时无法评价呢。"
                )
                return

            # 使用正则表达式解析返回的文本
            import re

            pattern = re.compile(
                r"(.*?)<affection:([+-]?\d+);coins:([+-]?\d+)>", re.DOTALL
            )
            match = pattern.search(response_text)

            if not match:
                logger.error(f"解析投喂评价失败。原始文本: '{response_text}'")
                # 如果解析失败，直接将 AI 的回复作为评价，并给予默认奖励
                evaluation = response_text
                affection_gain = 1
                coin_gain = 10
            else:
                evaluation = match.group(1).strip()
                affection_gain = int(match.group(2))
                coin_gain = int(match.group(3))

            await self.affection_service.add_affection_points(
                user_id, guild_id, affection_gain
            )

            # 只有当 coin_gain 是正数时才增加类脑币
            if coin_gain > 0:
                await self.coin_service.add_coins(user_id, coin_gain, reason="投喂奖励")

            # 替换表情并添加奖励消息
            evaluation_with_emojis = replace_emojis(evaluation)

            # 格式化系统提示，仅在获得奖励时显示
            system_message = ""
            if coin_gain > 0:
                system_message = f"> 你获得了 {coin_gain} 枚类脑币！"

            # 创建 Embed
            embed_description = evaluation_with_emojis
            if system_message:
                embed_description += f"\n\n{system_message}"

            embed = discord.Embed(
                description=embed_description,
                color=discord.Color.pink(),  # 你可以自定义颜色
            )

            # 设置作者信息
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url,
            )

            # 从配置中获取图片 URL
            # --- 动态获取图片 ---

            # 将用户上传的图片作为缩略图
            file = discord.File(fp=io.BytesIO(image_bytes), filename=image.filename)
            embed.set_thumbnail(url=f"attachment://{image.filename}")

            # 检查是否在豁免频道，如果是，则显示大图
            is_unrestricted = (
                interaction.channel.id in chat_config.UNRESTRICTED_CHANNEL_IDS
                or isinstance(interaction.channel, discord.Thread)
            )
            if is_unrestricted:
                sticker_url = FEEDING_CONFIG.get("RESPONSE_IMAGE_URL")
                if sticker_url:
                    embed.set_image(url=sticker_url)

            # 添加页脚用于上下文识别
            embed.set_footer(text="类脑娘对你的投喂做出回应...")

            # 记录投喂事件
            await self.feeding_service.record_feeding(user_id)

            await interaction.edit_original_response(
                content=None, embed=embed, attachments=[file]
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
