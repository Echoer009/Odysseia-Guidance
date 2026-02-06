# -*- coding: utf-8 -*-
import logging
import json
import sqlite3
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import discord

from src import config
from src.chat.config import chat_config
from src.chat.services.review_service import review_service
from src.chat.features.odysseia_coin.service.coin_service import coin_service
import asyncio

log = logging.getLogger(__name__)


class SubmissionService:
    """处理所有类型内容提交的服务"""

    def _get_db_connection(self):
        """获取世界书数据库的连接"""
        try:
            db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库失败: {e}", exc_info=True)
            return None

    async def _create_pending_entry(
        self,
        entry_type: str,
        interaction: discord.Interaction,
        entry_data: Dict[str, Any],
    ) -> Optional[int]:
        """
        将提交的数据作为待审核条目存入数据库。
        这是所有提交类型的通用内部方法。
        """
        conn = self._get_db_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()

            # --- 动态获取审核配置 ---
            review_config_key = ""
            if entry_type in ["general_knowledge", "community_member"]:
                review_config_key = "review_settings"
            elif entry_type == "work_event":
                review_config_key = "work_event_review_settings"

            if not review_config_key:
                log.error(f"未知的提交类型 '{entry_type}'，无法找到审核配置。")
                return None

            review_settings = chat_config.WORLD_BOOK_CONFIG.get(review_config_key, {})
            duration_minutes = review_settings.get(
                "review_duration_minutes", 1
            )  # 默认为1分钟
            expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)

            data_json = json.dumps(entry_data, ensure_ascii=False)

            cursor.execute(
                """
                INSERT INTO pending_entries
                (entry_type, data_json, channel_id, guild_id, proposer_id, expires_at, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry_type,
                    data_json,
                    interaction.channel_id,
                    interaction.guild_id,
                    interaction.user.id,
                    expires_at.isoformat(),
                    -1,  # 临时 message_id，将在审核服务中更新
                ),
            )

            pending_id = cursor.lastrowid
            conn.commit()
            log.info(
                f"已创建待审核条目 #{pending_id} (类型: {entry_type})，提交者: {interaction.user.id}"
            )
            return pending_id

        except sqlite3.Error as e:
            log.error(f"创建待审核条目时发生数据库错误: {e}", exc_info=True)
            conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    async def submit_general_knowledge(
        self,
        interaction: discord.Interaction,
        knowledge_data: Dict[str, Any],
        purchase_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        提交一条新的通用知识以供审核。

        Args:
            interaction: The discord interaction from the user.
            knowledge_data: A dict containing the knowledge details ('category_name', 'title', 'content_text', etc.).
            purchase_info: (Optional) A dict with purchase details if submitted via the shop.

        Returns:
            The ID of the pending entry if successful, otherwise None.
        """
        # 如果有购买信息，将其添加到主数据中以便于后续退款等操作
        if purchase_info:
            knowledge_data["purchase_info"] = purchase_info

        pending_id = await self._create_pending_entry(
            "general_knowledge", interaction, knowledge_data
        )

        if pending_id:
            # 调用 ReviewService 来启动审核流程
            assert review_service is not None
            asyncio.create_task(review_service.start_review(pending_id))
            log.info(f"通用知识提交成功，待审核ID: {pending_id}。已启动审核流程。")

        return pending_id

    async def submit_community_member(
        self,
        interaction: discord.Interaction,
        member_data: Dict[str, Any],
        purchase_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """处理社区成员档案的提交"""
        log.info(
            f"用户 {interaction.user.id} 正在提交社区成员档案: {member_data.get('name')}"
        )

        # 如果有购买信息，将其添加到 entry_data 中
        if purchase_info:
            member_data["purchase_info"] = purchase_info

        pending_id = await self._create_pending_entry(
            entry_type="community_member",
            interaction=interaction,
            entry_data=member_data,
        )

        if pending_id:
            # 异步启动审核流程，不阻塞当前交互
            assert review_service is not None
            asyncio.create_task(review_service.start_review(pending_id))
            log.info(
                f"已为社区成员档案 '{member_data.get('name')}' (pending_id: {pending_id}) 创建审核任务。"
            )

        return pending_id

    async def submit_personal_profile_from_purchase(
        self,
        interaction: discord.Interaction,
        profile_data: Dict[str, Any],
        purchase_info: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        处理从商店购买的个人档案提交，包含完整的扣款、验证和提交流程。

        Returns:
            A tuple of (success, message).
        """
        item_id = purchase_info.get("item_id")
        price = purchase_info.get("price")

        if not item_id or not price:
            log.error(f"个人档案购买信息不完整: item_id={item_id}, price={price}")
            return False, "❌ 内部错误：商品信息不完整，无法完成购买。"

        # 1. 扣款
        success, message, new_balance, _, _ = await coin_service.purchase_item(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id if interaction.guild else 0,
            item_id=item_id,
        )

        if not success:
            log.warning(
                f"用户 {interaction.user.id} 购买个人档案商品 (ID: {item_id}) 失败: {message}"
            )
            return False, f"购买失败：{message}"

        log.info(
            f"用户 {interaction.user.id} 成功购买个人档案商品，花费 {price}，新余额 {new_balance}。"
        )

        # 2. 验证数据 (虽然模态框里有基础验证，这里可以做更复杂的后端验证)
        # 在这个场景下，基本验证已足够

        # 3. 将购买信息添加到数据中，以便后续可能需要
        profile_data["purchase_info"] = purchase_info

        # 4. 创建待审核条目
        pending_id = await self._create_pending_entry(
            entry_type="community_member",
            interaction=interaction,
            entry_data=profile_data,
        )

        if not pending_id:
            # 如果创建失败，必须退款
            await coin_service.add_coins(
                user_id=interaction.user.id,
                amount=price,
                reason=f"个人档案提交审核失败自动退款 (item_id: {item_id})",
            )
            log.error(
                f"为用户 {interaction.user.id} 创建个人档案待审条目失败，已自动退款 {price}。"
            )
            return False, "❌ 提交审核时发生错误，你的购买费用已自动退还。"

        # 5. 启动审核流程
        assert review_service is not None
        asyncio.create_task(review_service.start_review(pending_id))
        log.info(
            f"已为用户 {interaction.user.id} 的个人档案 (pending_id: {pending_id}) 创建审核任务。"
        )

        return True, "✅ 你的名片已成功提交审核！审核通过后将自动生效。"

    async def submit_work_event(
        self,
        interaction: discord.Interaction,
        event_data: Dict[str, Any],
        purchase_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """提交一个新的自定义工作/卖屁股事件以供审核。"""
        if purchase_info:
            event_data["purchase_info"] = purchase_info

        pending_id = await self._create_pending_entry(
            "work_event", interaction, event_data
        )

        if pending_id:
            assert review_service is not None
            asyncio.create_task(review_service.start_review(pending_id))
            log.info(
                f"自定义工作事件提交成功，待审核ID: {pending_id}。已启动审核流程。"
            )

        return pending_id


# 创建 SubmissionService 的单例
submission_service = SubmissionService()
