# -*- coding: utf-8 -*-
import discord
from discord.ext import tasks
import logging
from typing import Dict, Any, Optional
import os
import json
import sqlite3
import re
import time
from datetime import datetime
import asyncio

from src import config
from src.chat.config import chat_config
from src.chat.features.world_book.services.incremental_rag_service import (
    incremental_rag_service,
)
from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)

# --- 审核配置 ---
REVIEW_SETTINGS = chat_config.WORLD_BOOK_CONFIG["review_settings"]
VOTE_EMOJI = REVIEW_SETTINGS["vote_emoji"]
REJECT_EMOJI = REVIEW_SETTINGS["reject_emoji"]


class ReviewService:
    """管理所有待审项目生命周期的服务"""

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")
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
                # 注意：社区成员的审核流程UI尚未完全分离，暂时复用通用知识的
                # 未来可以创建一个 _start_community_member_review
                await self._start_general_knowledge_review(entry, data)
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
            log.error(f"找不到提交时所在的频道 ID: {review_channel_id}")
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
                f"*审核将在{duration}分钟后自动结束。*"
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
            f"投票规则: {VOTE_EMOJI} 达到{approval_threshold}个通过 | "
            f"{VOTE_EMOJI} {duration}分钟内达到{instant_approval_threshold}个立即通过 | "
            f"{REJECT_EMOJI} 达到{rejection_threshold}个否决"
        )
        footer_text = f"提交者: {proposer.display_name} (ID: {proposer.id}) | 审核ID: {entry['id']} | {rules_text}"
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
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            log.warning(f"找不到消息 {payload.message_id}，可能已被删除。")
            return

        if not message.author.id == self.bot.user.id or not message.embeds:
            return

        embed = message.embeds[0]
        match = re.search(r"审核ID: (\d+)", embed.footer.text or "")
        if not match:
            return

        pending_id = int(match.group(1))
        log.debug(
            f"检测到对审核消息 (ID: {message.id}) 的投票，解析出 pending_id: {pending_id}"
        )
        await self.process_vote(pending_id, message)

    def _get_review_settings(self, entry_type: str) -> dict:
        """根据条目类型获取对应的审核配置"""
        if entry_type == "personal_profile":
            return chat_config.WORLD_BOOK_CONFIG.get(
                "personal_profile_review_settings", REVIEW_SETTINGS
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
        message: discord.Message,
        conn: sqlite3.Connection,
    ):
        """批准条目，将其写入主表并更新状态"""
        try:
            cursor = conn.cursor()
            data = json.loads(entry["data_json"])
            entry_type = entry["entry_type"]
            new_entry_id = None

            if entry_type == "general_knowledge":
                category_name = data["category_name"]
                cursor.execute(
                    "SELECT id FROM categories WHERE name = ?", (category_name,)
                )
                category_row = cursor.fetchone()
                if category_row:
                    category_id = category_row[0]
                else:
                    cursor.execute(
                        "INSERT INTO categories (name) VALUES (?)", (category_name,)
                    )
                    category_id = cursor.lastrowid

                content_dict = {"description": data["content_text"]}
                content_json = json.dumps(content_dict, ensure_ascii=False)
                clean_title = re.sub(r"[^\w\u4e00-\u9fff]", "_", data["title"])[:50]
                new_entry_id = f"{clean_title}_{int(time.time())}"

                cursor.execute(
                    "INSERT INTO general_knowledge (id, title, name, content_json, category_id, contributor_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                    (
                        new_entry_id,
                        data["title"],
                        data["name"],
                        content_json,
                        category_id,
                        data.get("contributor_id"),
                        "approved",
                    ),
                )
                log.info(
                    f"已创建通用知识条目 {new_entry_id} (源自审核 #{pending_id})。"
                )
                embed_title = "✅ 世界之书知识已入库"
                embed_description = f"感谢社区的审核！标题为 **{data['title']}** 的贡献已成功添加到世界之书中。"

            elif entry_type == "community_member":
                clean_name = re.sub(r"[^\w\u4e00-\u9fff]", "_", data["name"])[:50]
                new_entry_id = f"member_{clean_name}_{int(time.time())}"

                content_json_for_db = json.dumps(data, ensure_ascii=False)
                cursor.execute(
                    """
                    INSERT INTO community_members (id, title, discord_id, discord_number_id, content_json, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_entry_id,
                        data["name"],  # 将'name'插入到'title'列
                        data.get("discord_id"),
                        data.get("discord_number_id"),
                        content_json_for_db,
                        "approved",
                    ),
                )
                log.info(
                    f"已创建社区成员条目 {new_entry_id} (源自审核 #{pending_id})。"
                )

                nicknames = data.get("discord_nickname", [])
                if isinstance(nicknames, str):
                    nicknames = [
                        nick.strip() for nick in nicknames.split(",") if nick.strip()
                    ]

                if nicknames:
                    for nickname in nicknames:
                        cursor.execute(
                            "INSERT INTO member_discord_nicknames (member_id, nickname) VALUES (?, ?)",
                            (new_entry_id, nickname),
                        )
                    log.info(f"为成员 {new_entry_id} 插入了 {len(nicknames)} 个昵称。")

                embed_title = "✅ 社区成员档案已更新"
                embed_description = f"感谢大家的审核！ **{data['name']}** 的个人档案已经成功收录进世界之书！"

            if new_entry_id:
                cursor.execute(
                    "UPDATE pending_entries SET status = 'approved' WHERE id = ?",
                    (pending_id,),
                )
                conn.commit()
                log.info(f"审核条目 #{pending_id} 状态已更新为 'approved'。")

                if entry_type == "general_knowledge":
                    log.info(f"为新通用知识 {new_entry_id} 创建向量...")
                    asyncio.create_task(
                        incremental_rag_service.process_general_knowledge(new_entry_id)
                    )
                elif entry_type == "community_member":
                    log.info(f"为新社区成员档案 {new_entry_id} 创建向量...")
                    asyncio.create_task(
                        incremental_rag_service.process_community_member(new_entry_id)
                    )

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
                        title="【审核结果通知】",
                        description=f"抱歉，您提交的 **{data.get('name', '未知档案')}** 未能通过社区审核。",
                        color=discord.Color.red(),
                    )
                    embed.add_field(
                        name="退款通知",
                        value=f"您购买时支付的 **{price}** 类脑币已自动还到您的账户。",
                    )
                    embed.set_footer(text="感谢您的参与！")
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
                new_embed.title = "❌ 世界之书贡献"
                new_embed.description = (
                    f"标题为 **{data_name}** 的贡献提交未通过审核。\n**原因:** {reason}"
                )
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
                            entry["id"], entry, None, conn, "审核消息发送失败"
                        )
                        continue

                    channel = self.bot.get_channel(entry["channel_id"])
                    if not channel:
                        log.warning(
                            f"找不到频道 {entry['channel_id']}，无法处理过期条目 #{entry['id']}"
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
                            entry["id"], entry, message, conn, "审核时间结束，票数不足"
                        )
                except discord.NotFound:
                    log.warning(
                        f"找不到审核消息 {entry['message_id']}，将直接否决条目 #{entry['id']}"
                    )
                    await self.reject_entry(
                        entry["id"], entry, None, conn, "审核消息丢失"
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


def initialize_review_service(bot: discord.Client):
    """初始化并设置全局的 ReviewService 实例"""
    global review_service
    if review_service is None:
        review_service = ReviewService(bot)
        log.info("ReviewService 已成功初始化并启动定时任务。")
    return review_service
