import discord
from discord import app_commands
from discord.ext import commands
import re

from src.chat.config.chat_config import (
    CONFESSION_CONFIG,
    CONFESSION_PROMPT,
    CONFESSION_PERSONA_INJECTION,
)
from src.chat.config import chat_config
from src.chat.features.affection.service.affection_service import AffectionService
from src.chat.features.affection.service.confession_service import ConfessionService
from src.chat.services.gemini_service import gemini_service
from src.chat.services.prompt_service import prompt_service
from src.chat.utils.prompt_utils import replace_emojis
from src.config import DEVELOPER_USER_IDS
from src.chat.services.event_service import event_service
from src.chat.features.affection.utils.interaction_checks import (
    check_interaction_channel_availability,
)


class ConfessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.affection_service = AffectionService()
        self.confession_service = ConfessionService()

    @app_commands.command(
        name="忏悔", description="向类脑娘忏悔，或许能让她对你的态度改观一些?"
    )
    @app_commands.guild_only()
    @app_commands.rename(content="忏悔内容")
    @app_commands.describe(content="写下你的忏悔内容。")
    async def confess(self, interaction: discord.Interaction, content: str):
        # --- 交互可用性检查 ---
        is_allowed, error_message = await check_interaction_channel_availability(
            interaction
        )
        if not is_allowed:
            await interaction.response.send_message(error_message, ephemeral=True)
            return

        user_id_int = interaction.user.id
        user_id_str = str(user_id_int)

        # 检查用户是否为开发者，如果是，则绕过冷却时间检查
        if user_id_int not in DEVELOPER_USER_IDS:
            can_confess, remaining_time = await self.confession_service.can_confess(
                user_id_str
            )
            if not can_confess:
                await interaction.response.send_message(
                    f"{remaining_time}", ephemeral=True
                )
                return

        # 检查是否在豁免频道，以决定回复是否公开
        is_unrestricted = (
            interaction.channel_id in chat_config.UNRESTRICTED_CHANNEL_IDS
            or isinstance(interaction.channel, discord.Thread)
        )
        await interaction.response.defer(ephemeral=not is_unrestricted)

        try:
            affection_status = await self.affection_service.get_affection_status(
                user_id_int
            )
            current_affection = affection_status["points"]
            level_name = affection_status["level_name"]

            # 注入核心设定
            # 为忏悔场景创建一个特殊的、更宽容的人设
            # 1. 使用正则表达式移除审查模块和绝对规则模块
            system_prompt = prompt_service.get_prompt("SYSTEM_PROMPT") or ""
            persona_without_rules = re.sub(
                r"<ABSOLUTE_RULES>.*?</ABSOLUTE_RULES>",
                "",
                system_prompt,
                flags=re.DOTALL,
            )
            persona_without_moderation = re.sub(
                r"<content_moderation_guidelines>.*?</content_moderation_guidelines>",
                "",
                persona_without_rules,
                flags=re.DOTALL,
            )

            # 2. 移除 nsfw 关键词，避免触发API安全策略
            persona_without_nsfw = persona_without_moderation.replace("nsfw", "")

            # 3. 注入宽容的行为准则
            tolerant_persona = persona_without_nsfw.replace(
                "<behavioral_guidelines>",
                CONFESSION_PERSONA_INJECTION,
                1,
            )

            persona_prompt = tolerant_persona.format(
                current_time="",  # 在此场景下时间无关紧要
                user_name=interaction.user.display_name,
            )

            formatted_prompt = CONFESSION_PROMPT.format(
                persona=persona_prompt,
                user_name=interaction.user.display_name,
                confession_message=content,
                affection_level=level_name,
            )

            ai_response = await gemini_service.generate_confession_response(
                formatted_prompt
            )

            if not ai_response:
                await interaction.followup.send(
                    "类脑娘现在似乎不想听你的忏悔，请稍后再试。", ephemeral=True
                )
                return

            affection_change = 0
            match = re.search(r"<affection:([+-]?\d+)>", ai_response)
            if match:
                try:
                    affection_change = int(match.group(1))
                    ai_response = ai_response.replace(match.group(0), "").strip()
                except ValueError:
                    pass

            if current_affection >= 20:
                affection_change = 0

            new_affection = current_affection
            if affection_change > 0:
                new_affection = await self.affection_service.add_affection_points(
                    user_id_int, affection_change
                )

            await self.confession_service.record_confession(user_id_str)

            embed = discord.Embed(
                title="来自类脑娘的低语",
                description=replace_emojis(ai_response),
                color=discord.Color.purple(),
            )
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url,
            )

            if affection_change != 0:
                field_value = f"好感度 {'+' if affection_change > 0 else ''}{affection_change}\n当前好感度: {new_affection}"
                embed.add_field(name="好感度变化", value=field_value, inline=False)

            # --- 动态获取图片 ---
            image_url = CONFESSION_CONFIG.get("RESPONSE_IMAGE_URL")  # 默认图片
            selected_faction_id = event_service.get_selected_faction()
            if selected_faction_id:
                factions = event_service.get_event_factions()
                if factions:
                    for faction in factions:
                        if faction.get("faction_id") == selected_faction_id:
                            # 从新的 response_images 结构中获取忏悔专用的图片
                            image_url = faction.get("response_images", {}).get(
                                "confession", image_url
                            )
                            break

            if image_url:
                embed.set_thumbnail(url=image_url)

            embed.set_footer(text="类脑娘对你的忏悔做出了一些回应...")

            await interaction.followup.send(embed=embed, ephemeral=not is_unrestricted)

        except Exception as e:
            print(f"Error during confession: {e}")
            await interaction.followup.send(
                "处理你的忏悔时出现了一个意想不到的错误。", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionCog(bot))
