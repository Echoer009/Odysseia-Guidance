import discord
import logging
import sqlite3
import os
from typing import Dict, Any

from src import config
from src.chat.config import chat_config
from src.chat.features.world_book.services.world_book_service import world_book_service

log = logging.getLogger(__name__)

# 获取审核配置
REVIEW_SETTINGS = chat_config.WORLD_BOOK_CONFIG["review_settings"]
VOTE_EMOJI = REVIEW_SETTINGS["vote_emoji"]
REJECT_EMOJI = REVIEW_SETTINGS["reject_emoji"]


class CommunityMemberUploadModal(discord.ui.Modal, title="上传社区成员档案"):
    """用于用户上传社区成员档案的模态窗口"""

    def __init__(self, purchase_info: Dict[str, Any] = None):
        super().__init__()
        self.purchase_info = purchase_info

        # 成员名称输入框
        self.member_name_input = discord.ui.TextInput(
            label="成员名称",
            placeholder="请输入社区成员的名称或昵称",
            max_length=100,
            required=True,
        )
        self.add_item(self.member_name_input)

        # Discord ID输入框
        self.discord_id_input = discord.ui.TextInput(
            label="Discord ID",
            placeholder="请输入成员的Discord数字ID（必填）",
            max_length=20,
            required=True,
        )
        self.add_item(self.discord_id_input)

        # 性格特点输入框
        self.personality_input = discord.ui.TextInput(
            label="性格特点",
            placeholder="描述该成员的性格特点、行为方式等",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.personality_input)

        # 背景信息输入框
        self.background_input = discord.ui.TextInput(
            label="背景信息",
            placeholder="描述该成员的背景故事、经历等",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
        )
        self.add_item(self.background_input)

        # 喜好偏好输入框
        self.preferences_input = discord.ui.TextInput(
            label="喜好偏好",
            placeholder="描述该成员的喜好、兴趣、习惯等",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.add_item(self.preferences_input)

    def _get_world_book_connection(self):
        """获取世界书数据库的连接"""
        try:
            db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库失败: {e}", exc_info=True)
            return None

    async def on_submit(self, interaction: discord.Interaction):
        """当用户提交模态窗口时调用"""
        member_name = self.member_name_input.value.strip()
        discord_id = self.discord_id_input.value.strip()
        personality = self.personality_input.value.strip()
        background = self.background_input.value.strip()
        preferences = self.preferences_input.value.strip()

        # 首先进行输入验证
        if discord_id and not discord_id.isdigit():
            await interaction.response.send_message(
                "❌ Discord ID 必须为纯数字，请重新提交。", ephemeral=True
            )
            return

        if not member_name or not personality:
            await interaction.response.send_message(
                "成员名称和性格特点不能为空。", ephemeral=True
            )
            return

        # 验证通过后，延迟响应，以处理后续可能耗时的操作
        await interaction.response.defer(ephemeral=True)

        # --- 如果是通过商店购买，处理扣款 ---
        if self.purchase_info:
            from src.chat.features.odysseia_coin.service.coin_service import (
                coin_service,
            )

            price = self.purchase_info.get("price", 0)
            item_id = self.purchase_info.get("item_id")

            # 只有在价格大于0时才执行扣款
            if price > 0:
                new_balance = await coin_service.remove_coins(
                    user_id=interaction.user.id,
                    amount=price,
                    reason=f"购买社区成员档案上传位 (item_id: {item_id})",
                )

                if new_balance is None:
                    await interaction.followup.send(
                        "抱歉，你的余额似乎不足，购买失败。", ephemeral=True
                    )
                    return
        # --- 扣款逻辑结束 ---

        member_data = {
            "name": member_name,
            "discord_id": discord_id if discord_id else None,
            "personality": personality,
            "background": background if background else "未提供",
            "preferences": preferences if preferences else "未提供",
            "uploaded_by": interaction.user.id,
            "uploaded_by_name": interaction.user.display_name,
        }

        conn = self._get_world_book_connection()
        existing_entry_id = None
        if conn and discord_id:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM community_members WHERE discord_number_id = ? AND status = 'approved'",
                    (discord_id,),
                )
                row = cursor.fetchone()
                if row:
                    existing_entry_id = row["id"]
                    member_data["update_target_id"] = existing_entry_id
            except sqlite3.Error as e:
                log.error(f"查询现有社区成员时出错: {e}", exc_info=True)
            finally:
                conn.close()

        is_update = existing_entry_id is not None
        embed_title = "有人向我介绍了一位新朋友！"
        if is_update:
            embed_description = f"**{interaction.user.display_name}** 更新了关于 **{member_name}** 的一些信息，大家帮忙看看对不对。"
        else:
            embed_description = f"**{interaction.user.display_name}** 向我介绍了 **{member_name}**，大家也认识一下吧！"

        embed_fields = [
            {"name": "成员名称", "value": member_name, "inline": True},
        ]
        if discord_id:
            embed_fields.append(
                {"name": "Discord ID", "value": discord_id, "inline": True}
            )
        embed_fields.append(
            {
                "name": "性格特点",
                "value": personality[:300] + ("..." if len(personality) > 300 else ""),
                "inline": False,
            }
        )
        if background:
            embed_fields.append(
                {
                    "name": "背景信息",
                    "value": background[:200]
                    + ("..." if len(background) > 200 else ""),
                    "inline": False,
                }
            )
        if preferences:
            embed_fields.append(
                {
                    "name": "喜好偏好",
                    "value": preferences[:200]
                    + ("..." if len(preferences) > 200 else ""),
                    "inline": False,
                }
            )

        await world_book_service.initiate_review_process(
            interaction=interaction,
            entry_type="community_member",
            entry_data=member_data,
            review_settings=REVIEW_SETTINGS,
            embed_title=embed_title,
            embed_description=embed_description,
            embed_fields=embed_fields,
            is_update=is_update,
            purchase_info=self.purchase_info,  # 传递购买信息
        )
