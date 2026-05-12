# -*- coding: utf-8 -*-
import discord
from discord.ext import tasks
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
import weakref

if TYPE_CHECKING:
    from src.chat.features.work_game.services.work_db_service import WorkDBService
import os
import json
import sqlite3
import re
from datetime import datetime
from src.chat.features.admin_panel.services.db_services import (
    get_parade_db_connection,
    get_cursor,
)
import asyncio

from src import config
from src.chat.config import chat_config
from src.chat.features.world_book.services.incremental_rag_service import (
    incremental_rag_service,
)
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.work_game.services.work_db_service import WorkDBService

log = logging.getLogger(__name__)

# --- 审核配置 ---
REVIEW_SETTINGS = chat_config.WORLD_BOOK_CONFIG["review_settings"]
VOTE_EMOJI = REVIEW_SETTINGS["vote_emoji"]
REJECT_EMOJI = REVIEW_SETTINGS["reject_emoji"]


class ReviewService:
    """管理所有待审项目生命周期的服务"""

    def __init__(self, bot: discord.Client, work_db_service: "WorkDBService"):
        self.bot = bot
        self.db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")
        self.work_db_service = work_db_service
        self.background_tasks = weakref.WeakSet()
        self.check_expired_entries.start()

    def _get_db_connection(self):
        """建立并返回一个新的 SQLite 数据库连接。"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库失败: {e}", exc_info=True)
            return None

    async def start_review(self, pending_id: int):
        """根据 pending_id 发起一个公开审核流程"""
        conn = self._get_db_connection()
        if not conn:
            log.error(f"无法发起审核 for pending_id {pending_id}，数据库连接失败。")
            return

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_entries WHERE id = ?", (pending_id,))
            entry = cursor.fetchone()

            if not entry:
                log.error(f"在 start_review 中找不到待审核的条目 #{pending_id}。")
                return

            data = json.loads(entry["data_json"])
            entry_type = entry["entry_type"]

            if entry_type == "general_knowledge":
                await self._start_general_knowledge_review(entry, data)
            elif entry_type == "community_member":
                await self._start_community_member_review(entry, data)
            elif entry_type == "work_event":
                await self._start_work_event_review(entry, data)
            else:
                log.warning(
                    f"未知的审核条目类型: {entry_type} for pending_id: {pending_id}"
                )

        except Exception as e:
            log.error(f"发起审核流程时出错 (ID: {pending_id}): {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

    async def _start_general_knowledge_review(
        self, entry: sqlite3.Row, data: Dict[str, Any]
    ):
        """为通用知识条目发起审核"""
        proposer = await self.bot.fetch_user(entry["proposer_id"])

        embed = self._build_general_knowledge_embed(entry, data, proposer)

        # 从数据库记录中获取提交所在的频道ID
        review_channel_id = entry["channel_id"]
        channel = self.bot.get_channel(review_channel_id)
        if not channel:
            log.warning(
                f"无法找到频道 ID {review_channel_id}，审核无法发起（可能已被删除或机器人无权访问）。"
            )
            return
        if not isinstance(channel, discord.abc.Messageable):
            log.warning(
                f"频道 ID {review_channel_id} (类型: {type(channel)}) 不是一个可消息频道，审核无法发起。"
            )
            return

        review_message = await channel.send(embed=embed)

        await self._update_message_id(entry["id"], review_message.id)

    def _build_general_knowledge_embed(
        self, entry: sqlite3.Row, data: Dict[str, Any], proposer: discord.User
    ) -> discord.Embed:
        """构建通用知识提交的审核 Embed"""
        duration = REVIEW_SETTINGS["review_duration_minutes"]
        approval_threshold = REVIEW_SETTINGS["approval_threshold"]
        instant_approval_threshold = REVIEW_SETTINGS["instant_approval_threshold"]
        rejection_threshold = REVIEW_SETTINGS["rejection_threshold"]
        title = data.get("title", data.get("name", "未知标题"))
        content = data.get("content_text", data.get("description", ""))

        embed = discord.Embed(
            title="我收到了一张小纸条！",
            description=(
                f"**{proposer.display_name}** 递给我一张纸条，上面写着关于 **{title}** 的知识，大家觉得内容怎么样？\n\n"
                f"*咱有 {duration} 分钟的时间来决定哦！*"
            ),
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="类别", value=data.get("category_name", "社区成员"), inline=True
        )
        embed.add_field(name="标题", value=title, inline=False)

        # --- 优化内容预览 ---
        preview_content = ""
        if entry["entry_type"] == "community_member":
            preview_parts = []
            # 使用 .get(key) 获取值，如果不存在则为 None，在后续判断中会跳过
            personality = data.get("personality")
            background = data.get("background")
            preferences = data.get("preferences")

            if personality:
                preview_parts.append(f"**性格:** {personality}")
            if background:
                preview_parts.append(f"**背景:** {background}")
            if preferences:
                preview_parts.append(f"**偏好:** {preferences}")

            if preview_parts:
                preview_content = "\n".join(preview_parts)
            else:
                # 如果所有字段都为空，则显示提示
                preview_content = "没有提供额外信息。"
        else:
            # 对于通用知识，保持原有逻辑
            raw_content = content or json.dumps(data, ensure_ascii=False)
            preview_content = raw_content[:500] + (
                "..." if len(raw_content) > 500 else ""
            )

        embed.add_field(name="内容预览", value=preview_content, inline=False)

        rules_text = (
            f"投票小贴士: {VOTE_EMOJI} 达到{approval_threshold}个通过 | "
            f"{VOTE_EMOJI} {duration}分钟内达到{instant_approval_threshold}个立即通过 | "
            f"{REJECT_EMOJI} 达到{rejection_threshold}个否决"
        )
        footer_text = f"递纸条的人: {proposer.display_name} | 纸条ID: {entry['id']} | {rules_text}"
        embed.set_footer(text=footer_text)
        embed.timestamp = datetime.fromisoformat(entry["created_at"])
        return embed

    async def _start_community_member_review(
        self, entry: sqlite3.Row, data: Dict[str, Any]
    ):
        """为社区成员档案发起审核"""
        proposer = await self.bot.fetch_user(entry["proposer_id"])
        embed = self._build_community_member_embed(entry, data, proposer)

        review_channel_id = entry["channel_id"]
        channel = self.bot.get_channel(review_channel_id)
        if not channel:
            log.warning(
                f"无法找到频道 ID {review_channel_id}，审核无法发起（可能已被删除或机器人无权访问）。"
            )
            return
        if not isinstance(channel, discord.abc.Messageable):
            log.warning(
                f"频道 ID {review_channel_id} (类型: {type(channel)}) 不是一个可消息频道，审核无法发起。"
            )
            return

        review_message = await channel.send(embed=embed)
        await self._update_message_id(entry["id"], review_message.id)

    def _build_community_member_embed(
        self, entry: sqlite3.Row, data: Dict[str, Any], proposer: discord.User
    ) -> discord.Embed:
        """构建社区成员档案提交的审核 Embed"""
        review_settings = self._get_review_settings(entry["entry_type"])
        duration = review_settings["review_duration_minutes"]
        approval_threshold = review_settings["approval_threshold"]
        instant_approval_threshold = review_settings["instant_approval_threshold"]
        rejection_threshold = review_settings["rejection_threshold"]
        name = data.get("name", "未知姓名")

        # --- 判断是自我介绍还是他人介绍 ---
        is_self_introduction = str(data.get("discord_id")) == str(proposer.id)

        if is_self_introduction:
            title = "✨ 一份新的自我介绍！"
            description = (
                f"**{proposer.display_name}** 提交了一份关于自己的个人名片，大家快来看看吧！\n\n"
                f"*咱有 {duration} 分钟的时间来决定哦！*"
            )
        else:
            title = "💌 收到一份新的社区成员名片！"
            description = (
                f"**{proposer.display_name}** 向我介绍了一位新朋友 **{name}**，大家快来看看这份名片吧！\n\n"
                f"*咱有 {duration} 分钟的时间来决定哦！*"
            )

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
        )
        embed.add_field(name="类别", value="社区成员", inline=True)
        embed.add_field(name="姓名", value=name, inline=False)

        preview_parts = []
        personality = data.get("personality")
        background = data.get("background")
        preferences = data.get("preferences")

        if personality:
            preview_parts.append(f"**性格:** {personality}")
        if background:
            preview_parts.append(f"**背景:** {background}")
        if preferences:
            preview_parts.append(f"**偏好:** {preferences}")

        if preview_parts:
            preview_content = "\n".join(preview_parts)
            if len(preview_content) > 1024:
                preview_content = preview_content[:1021] + "..."
        else:
            preview_content = "没有提供额外信息。"

        embed.add_field(name="内容预览", value=preview_content, inline=False)

        rules_text = (
            f"投票小贴士: {VOTE_EMOJI} 达到{approval_threshold}个通过 | "
            f"{VOTE_EMOJI} {duration}分钟内达到{instant_approval_threshold}个立即通过 | "
            f"{REJECT_EMOJI} 达到{rejection_threshold}个否决"
        )
        footer_text = (
            f"推荐人: {proposer.display_name} | 名片ID: {entry['id']} | {rules_text}"
        )
        embed.set_footer(text=footer_text)
        embed.timestamp = datetime.fromisoformat(entry["created_at"])
        return embed

    async def _start_work_event_review(self, entry: sqlite3.Row, data: Dict[str, Any]):
        """为自定义工作事件发起审核"""
        proposer = await self.bot.fetch_user(entry["proposer_id"])
        embed = self._build_work_event_embed(entry, data, proposer)

        review_channel_id = entry["channel_id"]
        channel = self.bot.get_channel(review_channel_id)
        if not channel:
            log.warning(
                f"无法找到频道 ID {review_channel_id}，审核无法发起（可能已被删除或机器人无权访问）。"
            )
            return
        if not isinstance(channel, discord.abc.Messageable):
            log.warning(
                f"频道 ID {review_channel_id} (类型: {type(channel)}) 不是一个可消息频道，审核无法发起。"
            )
            return

        review_message = await channel.send(embed=embed)
        await self._update_message_id(entry["id"], review_message.id)

    def _build_work_event_embed(
        self, entry: sqlite3.Row, data: Dict[str, Any], proposer: discord.User
    ) -> discord.Embed:
        """构建自定义工作事件的审核 Embed"""
        review_settings = chat_config.WORLD_BOOK_CONFIG["work_event_review_settings"]
        duration = review_settings["review_duration_minutes"]

        embed = discord.Embed(
            title="🥵 拉皮条!",
            description=f"**{proposer.display_name}** 提交了一个新的事件，大家看看怎么样？\n\n*咱有 {duration} 分钟的时间来决定哦！*",
            color=discord.Color.from_rgb(255, 182, 193),  # Light Pink
        )

        embed.add_field(name="事件名称", value=data.get("name", "N/A"), inline=False)
        embed.add_field(name="描述", value=data.get("description", "N/A"), inline=False)
        embed.add_field(
            name="基础奖励",
            value=f"{data.get('reward_range_min')} - {data.get('reward_range_max')} 类脑币",
            inline=True,
        )

        if data.get("good_event_description"):
            embed.add_field(
                name="好事发生 ✅", value=data["good_event_description"], inline=False
            )
        if data.get("bad_event_description"):
            embed.add_field(
                name="坏事发生 ❌", value=data["bad_event_description"], inline=False
            )

        rules_text = (
            f"投票小贴士: {review_settings['vote_emoji']} 达到{review_settings['approval_threshold']}个通过 | "
            f"{review_settings['vote_emoji']} {duration}分钟内达到{review_settings['instant_approval_threshold']}个立即通过 | "
            f"{review_settings['reject_emoji']} 达到{review_settings['rejection_threshold']}个否决"
        )
        footer_text = (
            f"拉皮条的: {proposer.display_name} | 事件ID: {entry['id']} | {rules_text}"
        )
        embed.set_footer(text=footer_text)
        embed.timestamp = datetime.fromisoformat(entry["created_at"])
        return embed

    async def _update_message_id(self, pending_id: int, message_id: int):
        """更新待审核条目的 message_id"""
        conn = self._get_db_connection()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pending_entries SET message_id = ? WHERE id = ?",
                (message_id, pending_id),
            )
            conn.commit()
            log.info(f"已为待审核条目 #{pending_id} 更新 message_id 为 {message_id}")
        except sqlite3.Error as e:
            log.error(f"更新待审核条目的 message_id 时出错: {e}", exc_info=True)
            conn.rollback()
        finally:
            if conn:
                conn.close()

    async def handle_vote(self, payload: discord.RawReactionActionEvent):
        """处理来自Cog的投票事件"""
        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            log.warning(f"找不到消息 {payload.message_id}，可能已被删除。")
            return

        if (
            not self.bot.user
            or message.author.id != self.bot.user.id
            or not message.embeds
        ):
            return

        embed = message.embeds[0]
        match = re.search(r"(?:纸条|名片|事件)ID: (\d+)", embed.footer.text or "")
        if not match:
            return

        pending_id = int(match.group(1))
        log.debug(
            f"检测到对审核消息 (ID: {message.id}) 的投票，解析出 pending_id: {pending_id}"
        )
        await self.process_vote(pending_id, message)

    def _get_review_settings(self, entry_type: str) -> dict:
        """根据条目类型获取对应的审核配置"""
        if entry_type == "community_member":
            return chat_config.WORLD_BOOK_CONFIG.get(
                "personal_profile_review_settings", REVIEW_SETTINGS
            )
        elif entry_type == "work_event":
            return chat_config.WORLD_BOOK_CONFIG.get(
                "work_event_review_settings", REVIEW_SETTINGS
            )
        return REVIEW_SETTINGS

    async def process_vote(self, pending_id: int, message: discord.Message):
        """处理投票逻辑，检查是否达到阈值"""
        log.debug(f"--- 开始处理投票 for pending_id: {pending_id} ---")
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pending_entries WHERE id = ? AND status = 'pending'",
                (pending_id,),
            )
            entry = cursor.fetchone()

            if not entry:
                log.warning(
                    f"在 process_vote 中找不到待审核的条目 #{pending_id} 或其状态不是 'pending'。"
                )
                return

            review_settings = self._get_review_settings(entry["entry_type"])
            approvals = 0
            rejections = 0
            for reaction in message.reactions:
                if str(reaction.emoji) == review_settings["vote_emoji"]:
                    approvals = reaction.count
                elif str(reaction.emoji) == review_settings["reject_emoji"]:
                    rejections = reaction.count

            instant_approval_threshold = review_settings["instant_approval_threshold"]
            log.info(
                f"审核ID #{pending_id} (类型: {entry['entry_type']}): 当前票数 ✅{approvals}, ❌{rejections}。快速通过阈值: {instant_approval_threshold}"
            )

            if approvals >= instant_approval_threshold:
                log.info(f"审核ID #{pending_id} 达到快速通过阈值。准备批准...")
                await self.approve_entry(pending_id, entry, message, conn)
            elif rejections >= review_settings["rejection_threshold"]:
                log.info(f"审核ID #{pending_id} 达到否决阈值。")
                await self.reject_entry(
                    pending_id, entry, message, conn, "社区投票否决"
                )
            else:
                log.info(
                    f"审核ID #{pending_id} 票数未达到任何阈值，等待更多投票或过期。"
                )
        except Exception as e:
            log.error(f"处理投票时发生错误 (ID: {pending_id}): {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

    async def approve_entry(
        self,
        pending_id: int,
        entry: sqlite3.Row,
        message: Optional[discord.Message],
        conn: sqlite3.Connection,
    ):
        """批准条目，将其写入主表并更新状态"""
        try:
            cursor = conn.cursor()
            data = json.loads(entry["data_json"])
            entry_type = entry["entry_type"]
            new_entry_id = None

            parade_conn = None
            embed_title = "✅ 已通过审核"
            embed_description = "条目已成功通过审核。"
            try:
                parade_conn = get_parade_db_connection()
                if not parade_conn:
                    raise Exception("无法获取 Parade DB 连接。")
                parade_cursor = get_cursor(parade_conn)

                if entry_type == "general_knowledge":
                    # --- 准备写入 ParadeDB 的数据 ---
                    title = data.get("title", "无标题")
                    content_text = data.get("content_text", "")
                    category_name = data.get("category_name", "通用知识")
                    full_text = (
                        f"标题: {title}\n类别: {category_name}\n内容: {content_text}"
                    )
                    source_metadata = {
                        "category": category_name,
                        "source": "community_submission",
                        "contributor_id": str(entry["proposer_id"]),
                        "original_submission": data,
                    }
                    external_id = f"pending_{pending_id}"

                    # --- 执行插入 ---
                    parade_cursor.execute(
                        """
                        INSERT INTO general_knowledge.knowledge_documents
                        (external_id, title, full_text, source_metadata, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, NOW(), NOW())
                        RETURNING id
                        """,
                        (
                            external_id,
                            title,
                            full_text,
                            json.dumps(source_metadata, ensure_ascii=False),
                        ),
                    )
                    result = parade_cursor.fetchone()
                    if not result:
                        raise Exception("插入通用知识到 ParadeDB 后未能取回新 ID。")
                    new_entry_id = result["id"]
                    log.info(
                        f"已创建通用知识条目 {new_entry_id} 到 ParadeDB (源自审核 #{pending_id})。"
                    )
                    embed_title = "✅ 新知识Get！"
                    embed_description = f"大家的意见咱都收到啦！关于 **{data['title']}** 的新知识已经被我记在小本本上啦！"

                elif entry_type == "community_member":
                    profile_user_id = data.get("discord_id")
                    if not profile_user_id:
                        raise ValueError(
                            f"社区成员条目 #{pending_id} 缺少 discord_id。"
                        )

                    # --- 检查用户是否已有档案 ---
                    parade_cursor.execute(
                        "SELECT id FROM community.member_profiles WHERE discord_id = %s",
                        (str(profile_user_id),),
                    )
                    existing_member = parade_cursor.fetchone()

                    # --- 准备数据 ---
                    updated_name = data.get("name", "").strip()
                    full_text = f"""
名称: {updated_name}
Discord ID: {profile_user_id}
性格特点: {data.get("personality", "").strip()}
背景信息: {data.get("background", "").strip()}
喜好偏好: {data.get("preferences", "").strip()}
                    """.strip()
                    source_metadata = {
                        "name": updated_name,
                        "discord_id": str(profile_user_id),
                        "personality": data.get("personality", "").strip(),
                        "background": data.get("background", "").strip(),
                        "preferences": data.get("preferences", "").strip(),
                        "source": "community_submission",
                        "contributor_id": str(entry["proposer_id"]),
                        "original_submission": data,
                    }

                    if existing_member:
                        # --- 更新现有档案 ---
                        old_entry_id = existing_member["id"]
                        log.info(
                            f"检测到用户 {profile_user_id} 已有档案 (ID: {old_entry_id})，将执行更新操作。"
                        )
                        parade_cursor.execute(
                            """
                            UPDATE community.member_profiles
                            SET title = %s, full_text = %s, source_metadata = %s, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                updated_name,
                                full_text,
                                json.dumps(source_metadata, ensure_ascii=False),
                                old_entry_id,
                            ),
                        )
                        new_entry_id = old_entry_id
                        log.info(
                            f"已更新社区成员条目 {new_entry_id} (源自审核 #{pending_id})。"
                        )
                        # 异步删除旧向量，后续会创建新的
                        task = asyncio.create_task(
                            incremental_rag_service.delete_entry(new_entry_id)
                        )
                        self.background_tasks.add(task)
                        task.add_done_callback(self._handle_task_result)
                    else:
                        # --- 创建新档案 ---
                        external_id = f"pending_{pending_id}"
                        parade_cursor.execute(
                            """
                            INSERT INTO community.member_profiles (external_id, discord_id, title, full_text, source_metadata, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                            RETURNING id
                            """,
                            (
                                external_id,
                                str(profile_user_id),
                                updated_name,
                                full_text,
                                json.dumps(source_metadata, ensure_ascii=False),
                            ),
                        )
                        result = parade_cursor.fetchone()
                        if not result:
                            raise Exception("插入社区成员到 ParadeDB 后未能取回新 ID。")
                        new_entry_id = result["id"]
                        log.info(
                            f"已创建新的社区成员条目 {new_entry_id} (源自审核 #{pending_id})。"
                        )

                    embed_title = "✅ 新的名片已收录！"
                    embed_description = (
                        f"大家的意见咱都收到啦！ **{data['name']}** 我已经记住他们啦！"
                    )

                elif entry_type == "work_event":
                    # work_event 仍然使用 SQLite，保持原样
                    success = await self.work_db_service.add_custom_event(data)
                    if success:
                        new_entry_id = f"work_event_{data['name']}"  # 模拟ID
                        embed_title = "✅ 新活儿来啦！"
                        embed_description = f"好耶！**{data['name']}** 这个新事件已经被添加到事件池里啦，大家又有新活儿干了！"
                    else:
                        log.error(f"将自定义事件 #{pending_id} 添加到数据库时失败。")
                        # 此处 conn 是 SQLite conn，所以 rollback 是正确的
                        conn.rollback()
                        return

                # --- 统一提交和收尾 ---
                parade_conn.commit()

            except Exception as e:
                if parade_conn:
                    parade_conn.rollback()
                log.error(
                    f"在 ParadeDB 中批准条目 #{pending_id} 时出错: {e}", exc_info=True
                )
                # re-raise to let the outer try-except handle SQLite rollback and message update
                raise e
            finally:
                if parade_conn:
                    parade_conn.close()

            if new_entry_id:
                cursor.execute(
                    "UPDATE pending_entries SET status = 'approved' WHERE id = ?",
                    (pending_id,),
                )
                conn.commit()
                log.info(f"审核条目 #{pending_id} 状态已更新为 'approved'。")

                if entry_type == "general_knowledge":
                    log.info(f"为新通用知识 {new_entry_id} 创建向量...")
                    task = asyncio.create_task(
                        incremental_rag_service.process_general_knowledge(new_entry_id)
                    )
                    self.background_tasks.add(task)
                    task.add_done_callback(self._handle_task_result)
                elif entry_type == "community_member":
                    log.info(f"为新社区成员档案 {new_entry_id} 创建向量...")
                    task = asyncio.create_task(
                        incremental_rag_service.process_community_member(new_entry_id)
                    )
                    self.background_tasks.add(task)
                    task.add_done_callback(self._handle_task_result)

                if message:
                    original_embed = message.embeds[0]
                    new_embed = original_embed.copy()
                    new_embed.title = embed_title
                    new_embed.description = embed_description
                    new_embed.color = discord.Color.green()
                    await message.edit(embed=new_embed)
            else:
                log.warning(
                    f"无法识别的条目类型 '{entry_type}' (审核ID: {pending_id})，未执行任何操作。"
                )
                conn.rollback()
        except Exception as e:
            log.error(f"批准条目 #{pending_id} 时出错: {e}", exc_info=True)
            conn.rollback()

    def _handle_task_result(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # 任务被取消是正常情况
        except Exception as e:
            log.error(f"后台RAG任务执行失败: {e}", exc_info=True)

    async def _handle_refund(self, entry: sqlite3.Row):
        """处理审核失败的退款逻辑"""
        try:
            data = json.loads(entry["data_json"])
            purchase_info = data.get("purchase_info")
            if not purchase_info:
                return

            user_id = entry["proposer_id"]
            price = purchase_info.get("price")
            item_id = purchase_info.get("item_id")

            if user_id and price is not None:
                await coin_service.add_coins(
                    user_id=user_id,
                    amount=price,
                    reason=f"审核未通过自动退款 (审核ID: {entry['id']}, item_id: {item_id})",
                )
                log.info(f"已为用户 {user_id} 成功退款 {price} 类脑币。")
                try:
                    user = await self.bot.fetch_user(user_id)
                    embed = discord.Embed(
                        title="【呜...有个坏消息】",
                        description=f"那个...你提交的 **{data.get('name', '未知档案')}** 大家好像不太满意，没能通过...别灰心嘛！",
                        color=discord.Color.red(),
                    )
                    embed.add_field(
                        name="钱钱还你啦",
                        value=f"买这个花掉的 **{price}** 类脑币，我已经偷偷塞回你的口袋里啦。",
                    )
                    embed.set_footer(text="下次再试试看嘛！")
                    await user.send(embed=embed)
                    log.info(f"已向用户 {user_id} 发送退款通知。")
                except discord.Forbidden:
                    log.warning(f"无法向用户 {user_id} 发送私信（可能已关闭私信）。")
                except Exception as e:
                    log.error(
                        f"向用户 {user_id} 发送退款通知时出错: {e}", exc_info=True
                    )
        except Exception as e:
            log.error(
                f"处理退款逻辑时发生严重错误 (审核ID: {entry['id']}): {e}",
                exc_info=True,
            )

    async def reject_entry(
        self,
        pending_id: int,
        entry: sqlite3.Row,
        message: Optional[discord.Message],
        conn: sqlite3.Connection,
        reason: str,
    ):
        """否决条目并更新状态"""
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pending_entries SET status = 'rejected' WHERE id = ?",
                (pending_id,),
            )
            conn.commit()

            if message and message.embeds:
                original_embed = message.embeds[0]
                data_name = (
                    original_embed.fields[0].value
                    if original_embed.fields
                    else "未知贡献"
                )
                new_embed = original_embed.copy()
                new_embed.title = "❌ 这份投稿好像不太行..."
                new_embed.description = f"关于 **{data_name}** 的投稿没能通过大家的考验... \n**原因:** {reason}"
                new_embed.color = discord.Color.red()
                await message.edit(embed=new_embed)

            log.info(f"审核ID #{pending_id} 已被否决，原因: {reason}")
            await self._handle_refund(entry)
        except Exception as e:
            log.error(f"否决条目 #{pending_id} 时出错: {e}", exc_info=True)
            conn.rollback()

    @tasks.loop(minutes=1)
    async def check_expired_entries(self):
        """每分钟检查一次已到期的审核条目"""
        await self.bot.wait_until_ready()
        log.debug("开始检查过期的审核条目...")

        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            now_iso = datetime.utcnow().isoformat()
            cursor.execute(
                "SELECT * FROM pending_entries WHERE status = 'pending' AND expires_at <= ?",
                (now_iso,),
            )
            expired_entries = cursor.fetchall()

            if not expired_entries:
                log.debug("没有找到过期的审核条目。")
                return

            log.info(f"找到 {len(expired_entries)} 个过期的审核条目，正在处理...")
            for entry in expired_entries:
                try:
                    # 检查 message_id 是否有效
                    if not entry["message_id"] or entry["message_id"] <= 0:
                        log.warning(
                            f"过期条目 #{entry['id']} 有一个无效的 message_id ({entry['message_id']})。将直接否决。"
                        )
                        await self.reject_entry(
                            entry["id"],
                            entry,
                            None,
                            conn,
                            "呜，我好像把投票消息弄丢了...",
                        )
                        continue

                    channel = self.bot.get_channel(entry["channel_id"])
                    if not channel:
                        log.warning(
                            f"无法找到频道 {entry['channel_id']}，无法处理过期条目 #{entry['id']}。这是一个过时的数据，将直接删除。"
                        )
                        # 直接从数据库中删除这个过时的条目
                        cursor.execute(
                            "DELETE FROM pending_entries WHERE id = ?", (entry["id"],)
                        )
                        conn.commit()
                        log.info(f"已删除过时的待审核条目 #{entry['id']}。")
                        continue

                    if not isinstance(channel, discord.abc.Messageable):
                        log.warning(
                            f"频道 {entry['channel_id']} (类型: {type(channel)}) 不是可消息频道，无法处理过期条目 #{entry['id']}"
                        )
                        continue

                    message = await channel.fetch_message(entry["message_id"])
                    approvals = 0
                    for reaction in message.reactions:
                        if str(reaction.emoji) == VOTE_EMOJI:
                            async for user in reaction.users():
                                if not user.bot:
                                    approvals += 1
                            break

                    review_settings = self._get_review_settings(entry["entry_type"])
                    log.info(
                        f"过期审核ID #{entry['id']} (类型: {entry['entry_type']}): 最终真实用户票数 ✅{approvals}。通过阈值: {review_settings['approval_threshold']}"
                    )

                    if approvals >= review_settings["approval_threshold"]:
                        log.info(f"过期审核ID #{entry['id']} 满足通过条件。")
                        await self.approve_entry(entry["id"], entry, message, conn)
                    else:
                        log.info(f"过期审核ID #{entry['id']} 未满足通过条件。")
                        await self.reject_entry(
                            entry["id"],
                            entry,
                            message,
                            conn,
                            "时间到了，但是大家好像还没决定好...",
                        )
                except discord.NotFound:
                    log.warning(
                        f"找不到审核消息 {entry['message_id']}，将直接否决条目 #{entry['id']}"
                    )
                    await self.reject_entry(
                        entry["id"], entry, None, conn, "哎呀，投票消息不见了！"
                    )
                except Exception as e:
                    log.error(
                        f"处理过期条目 #{entry['id']} 时发生错误: {e}", exc_info=True
                    )
        except Exception as e:
            log.error(f"检查过期条目时发生数据库错误: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()


# --- 单例模式 ---
review_service: Optional["ReviewService"] = None


def initialize_review_service(bot: discord.Client, work_db_service: "WorkDBService"):
    """初始化并设置全局的 ReviewService 实例"""
    global review_service
    if review_service is None:
        review_service = ReviewService(bot, work_db_service)
        log.info("ReviewService 已成功初始化并启动定时任务。")
    return review_service
