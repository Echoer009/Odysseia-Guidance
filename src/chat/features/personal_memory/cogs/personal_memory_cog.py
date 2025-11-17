import discord
from discord.ext import commands
import logging
import sqlite3
import os

from src import config
from src.chat.config import chat_config
from ..services.personal_memory_service import personal_memory_service
from ..ui.profile_modal import PROFILE_MODAL_CUSTOM_ID
from src.chat.features.world_book.services.world_book_service import world_book_service

log = logging.getLogger(__name__)


class PersonalMemoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = personal_memory_service
        self.world_book_db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")

    def _get_world_book_connection(self):
        try:
            conn = sqlite3.connect(self.world_book_db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库失败: {e}", exc_info=True)
            return None

    @commands.Cog.listener("on_interaction")
    async def on_modal_submit(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.modal_submit:
            return

        custom_id = interaction.data.get("custom_id")
        if custom_id != PROFILE_MODAL_CUSTOM_ID:
            return

        try:
            await interaction.response.defer(ephemeral=True)

            components = interaction.data.get("components", [])
            values_by_id = {
                comp["components"][0]["custom_id"]: comp["components"][0]["value"]
                for comp in components
                if comp.get("components")
            }

            profile_data = {
                "name": values_by_id.get("name", "").strip(),
                "personality": values_by_id.get("personality", "").strip(),
                "background": values_by_id.get("background", "").strip(),
                "preferences": values_by_id.get("preferences", "").strip(),
                "discord_id": str(interaction.user.id),
                "uploaded_by": interaction.user.id,
                "uploaded_by_name": interaction.user.display_name,
            }

            if not profile_data["name"] or not profile_data["personality"]:
                await interaction.followup.send(
                    "名称和性格特点不能为空。", ephemeral=True
                )
                return

            # --- 新增：检查是创建还是更新 ---
            is_update = False
            conn = self._get_world_book_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM community_members WHERE discord_number_id = ?",
                        (str(interaction.user.id),),
                    )
                    if cursor.fetchone():
                        is_update = True
                        log.info(
                            f"检测到用户 {interaction.user.id} 的个人档案更新请求。"
                        )
                except sqlite3.Error as e:
                    log.error(f"查询现有个人档案时出错: {e}", exc_info=True)
                finally:
                    conn.close()

            profile_data["update_target_id"] = str(interaction.user.id)

            review_settings = chat_config.WORLD_BOOK_CONFIG[
                "personal_profile_review_settings"
            ]

            embed_title = "我收到了一张新名片！"
            if is_update:
                embed_description = f"**{interaction.user.display_name}** 给我了一张TA的新名片，大伙怎么看?"
            else:
                embed_description = f"**{interaction.user.display_name}** 递给了我一张TA的名片，大伙怎么看?"

            embed_fields = [
                {"name": "名称", "value": profile_data["name"], "inline": True},
                {
                    "name": "性格特点",
                    "value": profile_data["personality"][:300]
                    + ("..." if len(profile_data["personality"]) > 300 else ""),
                    "inline": False,
                },
            ]
            if profile_data["background"]:
                embed_fields.append(
                    {
                        "name": "背景信息",
                        "value": profile_data["background"][:200]
                        + ("..." if len(profile_data["background"]) > 200 else ""),
                        "inline": False,
                    }
                )
            if profile_data["preferences"]:
                embed_fields.append(
                    {
                        "name": "喜好偏好",
                        "value": profile_data["preferences"][:200]
                        + ("..." if len(profile_data["preferences"]) > 200 else ""),
                        "inline": False,
                    }
                )

            await world_book_service.initiate_review_process(
                interaction=interaction,
                entry_type="personal_profile",
                entry_data=profile_data,
                review_settings=review_settings,
                embed_title=embed_title,
                embed_description=embed_description,
                embed_fields=embed_fields,
                is_update=is_update,
            )
            log.info(
                f"用户 {interaction.user.id} 的个人档案已提交审核 (更新: {is_update})。"
            )

        except Exception as e:
            log.error(
                f"处理用户 {interaction.user.id} 的个人档案提交时出错: {e}",
                exc_info=True,
            )
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "提交你的档案时发生了未知错误，请稍后再试。", ephemeral=True
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(PersonalMemoryCog(bot))
