# -*- coding: utf-8 -*-

import discord
import logging
import asyncio
from typing import Any, Dict, Mapping
from sqlalchemy import select, func

from .base_view import BaseTableView
from ..modals.search_modals import SearchVectorDBModal
from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.config import chat_config
from src.database.database import AsyncSessionLocal
from src.database.models import ForumThread

log = logging.getLogger(__name__)


class VectorDBView(BaseTableView):
    def __init__(
        self, author_id: int, message: discord.Message, parent_view: discord.ui.View
    ):
        super().__init__(author_id, message, parent_view)
        self.current_table = "vector_db_metadata"  # 虚拟表名
        # 修复类型不匹配：允许 current_list_items 存储字典
        self.current_list_items: list[Dict[str, Any]] = []

    def _get_entry_title(self, entry: Mapping[str, Any]) -> str:
        try:
            metadata = entry.get("metadata", {})
            title = metadata.get("thread_name", "无标题")
            author_name = metadata.get("author_name", "未知作者")
            return f"标题: {title} - 作者: {author_name}"
        except Exception as e:
            log.warning(f"解析向量条目时出错: {e}")
            return f"ID: #{entry.get('id', 'N/A')}"

    def _add_search_buttons(self):
        if not self.search_mode:
            self.search_button = discord.ui.Button(
                label="关键词搜索",
                emoji="🔍",
                style=discord.ButtonStyle.primary,
                row=1,
            )
            self.search_button.callback = self.search_vector_db
            self.add_item(self.search_button)

        self.query_missing_button = discord.ui.Button(
            label="查询缺失帖子", emoji="🔎", style=discord.ButtonStyle.success, row=2
        )
        self.query_missing_button.callback = self.query_missing_threads
        self.add_item(self.query_missing_button)

        self.index_missing_button = discord.ui.Button(
            label="索引缺失帖子", emoji="➕", style=discord.ButtonStyle.danger, row=2
        )
        self.index_missing_button.callback = self.index_missing_threads
        self.add_item(self.index_missing_button)

    def _add_detail_view_components(self):
        # 详情视图只有返回列表和返回主菜单
        self.back_button = discord.ui.Button(
            label="返回列表", emoji="⬅️", style=discord.ButtonStyle.secondary
        )
        self.back_button.callback = self.go_to_list_view
        self.add_item(self.back_button)

    async def search_vector_db(self, interaction: discord.Interaction):
        modal = SearchVectorDBModal(self)
        await interaction.response.send_modal(modal)

    async def query_missing_threads(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⏳ 正在开始查询，这可能需要几分钟时间，请稍候...", ephemeral=True
        )
        try:
            bot = interaction.client
            all_forum_thread_ids = set()
            for channel_id in chat_config.FORUM_SEARCH_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if isinstance(channel, discord.ForumChannel):
                    async for thread in channel.archived_threads(limit=None):
                        all_forum_thread_ids.add(thread.id)
                    for thread in channel.threads:
                        all_forum_thread_ids.add(thread.id)

            indexed_thread_ids = set(
                await forum_vector_db_service.get_all_indexed_thread_ids()
            )
            missing_thread_ids = all_forum_thread_ids - indexed_thread_ids
            missing_count = len(missing_thread_ids)

            if missing_count == 0:
                await interaction.followup.send("✅ 所有帖子均已索引。", ephemeral=True)
            else:
                await interaction.followup.send(
                    f"⚠️ 发现 **{missing_count}** 个帖子尚未索引。", ephemeral=True
                )
        except Exception as e:
            log.error(f"查询缺失帖子时出错: {e}", exc_info=True)
            await interaction.followup.send(f"查询时发生错误: {e}", ephemeral=True)

    async def index_missing_threads(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⏳ **任务已启动**\n\n正在后台开始索引所有缺失的帖子。", ephemeral=True
        )
        asyncio.create_task(self._background_index_task(interaction))

    async def _background_index_task(self, interaction: discord.Interaction):
        """后台索引缺失帖子的任务"""
        try:
            bot = interaction.client
            from src.chat.features.forum_search.services.forum_search_service import (
                forum_search_service,
            )

            # 获取所有应该索引的帖子
            all_forum_threads = []
            for channel_id in chat_config.FORUM_SEARCH_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if isinstance(channel, discord.ForumChannel):
                    async for thread in channel.archived_threads(limit=None):
                        all_forum_threads.append(thread)
                    for thread in channel.threads:
                        all_forum_threads.append(thread)

            # 获取已索引的帖子
            indexed_thread_ids = set(
                await forum_vector_db_service.get_all_indexed_thread_ids()
            )

            # 过滤出缺失的帖子
            missing_threads = [
                t for t in all_forum_threads if t.id not in indexed_thread_ids
            ]

            if not missing_threads:
                await interaction.followup.send(
                    "✅ 没有需要索引的帖子。", ephemeral=True
                )
                return

            # 索引缺失的帖子
            success_count = 0
            for thread in missing_threads:
                try:
                    await forum_search_service.process_thread(thread)
                    success_count += 1
                    if success_count % 10 == 0:
                        await interaction.followup.send(
                            f"已索引 {success_count}/{len(missing_threads)} 个帖子...",
                            ephemeral=True,
                        )
                except Exception as e:
                    log.error(f"索引帖子 {thread.id} 时出错: {e}", exc_info=True)

            await interaction.followup.send(
                f"✅ 索引完成！成功索引 {success_count}/{len(missing_threads)} 个帖子。",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"后台索引任务出错: {e}", exc_info=True)
            await interaction.followup.send(f"索引过程中发生错误: {e}", ephemeral=True)

    async def _build_list_embed(self) -> discord.Embed:
        table_display_name = "向量库元数据 (帖子搜索)"
        try:
            if (
                not forum_vector_db_service
                or not forum_vector_db_service.is_available()
            ):
                raise ConnectionError("未能连接到向量数据库服务。")

            if self.search_mode:
                total_items = len(self.current_list_items)
                start_idx = self.current_page * self.items_per_page
                end_idx = start_idx + self.items_per_page
                page_items = self.current_list_items[start_idx:end_idx]
                embed = discord.Embed(
                    title=f"搜索: {table_display_name} (关键词: '{self.search_keyword}')",
                    color=discord.Color.gold(),
                )
            else:
                # 从 ParadeDB 获取总数量和分页数据
                async with AsyncSessionLocal() as session:
                    # 获取总数
                    total_result = await session.execute(
                        select(func.count(ForumThread.id))
                    )
                    total_items = total_result.scalar() or 0

                    # 获取分页数据
                    offset = self.current_page * self.items_per_page
                    result = await session.execute(
                        select(ForumThread)
                        .order_by(ForumThread.created_at.desc())
                        .offset(offset)
                        .limit(self.items_per_page)
                    )
                    threads = result.scalars().all()

                    page_items = []
                    for thread in threads:
                        page_items.append(
                            {
                                "id": thread.thread_id,
                                "metadata": {
                                    "thread_id": thread.thread_id,
                                    "thread_name": thread.thread_name,
                                    "author_name": thread.author_name,
                                    "author_id": thread.author_id,
                                    "category_name": thread.category_name,
                                    "channel_id": thread.channel_id,
                                    "guild_id": thread.guild_id,
                                    "created_at": (
                                        thread.created_at.isoformat()
                                        if thread.created_at
                                        else None
                                    ),
                                },
                            }
                        )

                self.current_list_items = page_items
                embed = discord.Embed(
                    title=f"浏览: {table_display_name}", color=discord.Color.purple()
                )

            self.total_pages = (
                total_items + self.items_per_page - 1
            ) // self.items_per_page

            if not self.current_list_items:
                embed.description = "数据库中没有找到任何条目。"
            else:
                list_text = "\n".join(
                    [
                        f"**`#{item.get('id', 'N/A')}`** - {self._get_entry_title(item)}"
                        for item in page_items
                    ]
                )
                embed.description = list_text

            embed.set_footer(
                text=f"第 {self.current_page + 1} / {self.total_pages or 1} 页 (共 {total_items} 条)"
            )
            return embed
        except Exception as e:
            log.error(f"构建向量数据库列表视图时出错: {e}", exc_info=True)
            return discord.Embed(
                title="错误",
                description=f"加载向量数据库时发生错误: {e}",
                color=discord.Color.red(),
            )

    async def _build_detail_embed(self) -> discord.Embed:
        """构建详情视图的 Embed"""
        if not self.current_list_items or not self.current_item_id:
            return discord.Embed(
                title="错误",
                description="没有选择任何条目。",
                color=discord.Color.red(),
            )

        try:
            # 根据 current_item_id 找到对应的条目
            entry = next(
                (
                    item
                    for item in self.current_list_items
                    if str(item.get("id")) == str(self.current_item_id)
                ),
                None,
            )
            if not entry:
                return discord.Embed(
                    title="错误",
                    description="未找到选中的条目。",
                    color=discord.Color.red(),
                )

            metadata = entry.get("metadata", {})

            embed = discord.Embed(
                title=f"帖子详情: {metadata.get('thread_name', '无标题')}",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="帖子 ID",
                value=f"`{metadata.get('thread_id', 'N/A')}`",
                inline=True,
            )
            embed.add_field(
                name="作者",
                value=f"{metadata.get('author_name', '未知')} ({metadata.get('author_id', 'N/A')})",
                inline=True,
            )
            embed.add_field(
                name="分类",
                value=metadata.get("category_name", "未知"),
                inline=True,
            )
            embed.add_field(
                name="频道 ID",
                value=f"`{metadata.get('channel_id', 'N/A')}`",
                inline=True,
            )
            embed.add_field(
                name="服务器 ID",
                value=f"`{metadata.get('guild_id', 'N/A')}`",
                inline=True,
            )
            embed.add_field(
                name="创建时间",
                value=metadata.get("created_at", "未知"),
                inline=False,
            )

            if "distance" in entry:
                embed.add_field(
                    name="相似度距离",
                    value=f"{entry['distance']:.4f}",
                    inline=False,
                )

            return embed
        except Exception as e:
            log.error(f"构建详情视图时出错: {e}", exc_info=True)
            return discord.Embed(
                title="错误",
                description=f"加载详情时发生错误: {e}",
                color=discord.Color.red(),
            )
