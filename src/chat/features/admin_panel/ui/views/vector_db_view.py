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

        # 查询失效帖子按钮
        self.query_deleted_button = discord.ui.Button(
            label="查询失效帖子", emoji="🔍", style=discord.ButtonStyle.danger, row=2
        )
        self.query_deleted_button.callback = self.query_deleted_threads
        self.add_item(self.query_deleted_button)

    def _add_detail_view_components(self):
        # 详情视图只有返回列表和返回主菜单
        self.back_button = discord.ui.Button(
            label="返回列表", emoji="⬅️", style=discord.ButtonStyle.secondary
        )
        self.back_button.callback = self.go_to_list_view
        self.add_item(self.back_button)

        # 添加删除按钮
        self.delete_button = discord.ui.Button(
            label="删除帖子", emoji="🗑️", style=discord.ButtonStyle.danger
        )
        self.delete_button.callback = self.delete_thread
        self.add_item(self.delete_button)

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

                    # 获取 BGE/Qwen embedding 统计
                    bge_count_result = await session.execute(
                        select(func.count(ForumThread.id)).where(
                            ForumThread.bge_embedding.isnot(None)
                        )
                    )
                    bge_count = bge_count_result.scalar() or 0

                    qwen_count_result = await session.execute(
                        select(func.count(ForumThread.id)).where(
                            ForumThread.qwen_embedding.isnot(None)
                        )
                    )
                    qwen_count = qwen_count_result.scalar() or 0

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
                                "content": thread.content or "",  # 添加正文内容
                                "has_bge": thread.bge_embedding is not None,
                                "has_qwen": thread.qwen_embedding is not None,
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

                # 添加 embedding 统计信息
                embed.add_field(
                    name="📊 Embedding 统计",
                    value=f"🟢 BGE: {bge_count}/{total_items} | 🔵 Qwen: {qwen_count}/{total_items}",
                    inline=False,
                )

            self.total_pages = (
                total_items + self.items_per_page - 1
            ) // self.items_per_page

            if not self.current_list_items:
                embed.description = "数据库中没有找到任何条目。"
            else:
                list_text = "\n".join(
                    [
                        f"**`#{item.get('id', 'N/A')}`** {self._get_embedding_status(item)} - {self._get_entry_title(item)}"
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

    def _get_embedding_status(self, item: Dict[str, Any]) -> str:
        """获取条目的 embedding 状态图标"""
        has_bge = item.get("has_bge", False)
        has_qwen = item.get("has_qwen", False)

        if has_bge and has_qwen:
            return "🟢🔵"  # 两种都有
        elif has_bge:
            return "🟢"  # 只有 BGE
        elif has_qwen:
            return "🔵"  # 只有 Qwen
        else:
            return "⚪"  # 都没有

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

            # 添加 Embedding 状态
            has_bge = entry.get("has_bge", False)
            has_qwen = entry.get("has_qwen", False)
            bge_status = "✅ 已生成" if has_bge else "❌ 未生成"
            qwen_status = "✅ 已生成" if has_qwen else "❌ 未生成"
            embed.add_field(
                name="🟢 BGE Embedding",
                value=bge_status,
                inline=True,
            )
            embed.add_field(
                name="🔵 Qwen Embedding",
                value=qwen_status,
                inline=True,
            )

            # 添加帖子正文内容
            content = entry.get("content", "")
            if content:
                # Discord Embed 字段值最大 1024 字符，截断处理
                if len(content) > 1000:
                    content = content[:1000] + "..."
                embed.add_field(
                    name="正文内容",
                    value=content,
                    inline=False,
                )
            else:
                embed.add_field(
                    name="正文内容",
                    value="*(无内容或内容为空)*",
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

    async def delete_thread(self, interaction: discord.Interaction):
        """删除当前选中的帖子（从数据库中删除）"""
        if not self.current_item_id:
            return await interaction.response.send_message(
                "没有可删除的条目。", ephemeral=True
            )

        thread_id = self.current_item_id

        # 确认删除视图
        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            try:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        # 查找并删除帖子
                        result = await session.execute(
                            select(ForumThread).where(
                                ForumThread.thread_id == int(thread_id)
                            )
                        )
                        thread_to_delete = result.scalar_one_or_none()

                        if thread_to_delete:
                            await session.delete(thread_to_delete)
                            log.info(
                                f"管理员 {interaction.user.display_name} 删除了帖子 {thread_id}"
                            )
                            await interaction.response.edit_message(
                                content=f"🗑️ 帖子 `{thread_id}` 已从向量数据库中删除。",
                                view=None,
                            )
                            # 返回列表视图
                            self.view_mode = "list"
                            self.current_item_id = None
                            await self.update_view()
                        else:
                            await interaction.response.edit_message(
                                content=f"❌ 找不到帖子 `{thread_id}`。", view=None
                            )
            except Exception as e:
                log.error(f"删除帖子时出错: {e}", exc_info=True)
                await interaction.response.edit_message(
                    content=f"删除失败: {e}", view=None
                )

        async def cancel_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(
                content="删除操作已取消。", view=None
            )

        confirm_button = discord.ui.Button(
            label="确认删除", style=discord.ButtonStyle.danger
        )
        confirm_button.callback = confirm_callback
        cancel_button = discord.ui.Button(
            label="取消", style=discord.ButtonStyle.secondary
        )
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.response.send_message(
            f"**⚠️ 确认删除**\n你确定要从向量数据库中删除帖子 `{thread_id}` 吗？\n\n**注意**：这只会删除向量数据库中的记录，不会删除 Discord 上的原帖子。",
            view=confirm_view,
            ephemeral=True,
        )

    async def query_deleted_threads(self, interaction: discord.Interaction):
        """查询并显示数据库中已删除的帖子（支持分页、链接跳转、确认清理）"""
        await interaction.response.send_message(
            "⏳ 正在查询失效帖子，这可能需要几分钟时间，请稍候...", ephemeral=True
        )

        try:
            # 导入清理服务
            from src.chat.features.forum_search.cogs.forum_cleanup_cog import (
                forum_cleanup_cog,
            )

            if forum_cleanup_cog is None:
                if interaction.message:
                    await interaction.followup.edit_message(
                        interaction.message.id,
                        content="❌ 清理服务未初始化，请稍后重试。",
                    )
                return

            # 获取所有频道的失效帖子预览
            all_deleted_threads = []
            for channel_id in chat_config.FORUM_SEARCH_CHANNEL_IDS:
                result = await forum_cleanup_cog.get_deleted_threads_preview(channel_id)
                # 跳过无效频道或没有失效帖子的情况
                if not result or not result.get("deleted_threads_info"):
                    continue
                channel_name = result.get("channel_name", f"频道{channel_id}")
                for thread in result["deleted_threads_info"]:
                    thread["channel_name"] = channel_name
                    thread["channel_id"] = channel_id
                    all_deleted_threads.append(thread)

            if not all_deleted_threads:
                if interaction.message:
                    await interaction.followup.edit_message(
                        interaction.message.id,
                        content="✅ 没有发现失效帖子，数据库中的帖子都是有效的。",
                    )
                return

            # 创建分页视图
            view = DeletedThreadsPaginationView(
                all_deleted_threads, interaction.user.id, interaction.guild_id
            )
            embed = view.build_embed()
            if interaction.message:
                await interaction.followup.edit_message(
                    interaction.message.id,
                    content=None,
                    embed=embed,
                    view=view,
                )

        except Exception as e:
            log.error(f"查询失效帖子时出错: {e}", exc_info=True)
            if interaction.message:
                await interaction.followup.edit_message(
                    interaction.message.id,
                    content=f"❌ 查询过程中发生错误: {e}",
                )


class DeletedThreadsPaginationView(discord.ui.View):
    """失效帖子分页视图 - 支持分页浏览、链接跳转、确认清理"""

    def __init__(
        self,
        deleted_threads: list[Dict[str, Any]],
        author_id: int,
        guild_id: int | None,
        page_size: int = 5,
    ):
        super().__init__(timeout=300)  # 5分钟超时
        self.deleted_threads = deleted_threads
        self.author_id = author_id
        self.guild_id = guild_id
        self.page_size = page_size
        self.current_page = 0
        self.total_pages = (len(deleted_threads) + page_size - 1) // page_size

        self._update_buttons()

    def _update_buttons(self):
        """更新按钮状态"""
        self.clear_items()

        # 分页按钮
        if self.current_page > 0:
            prev_btn = discord.ui.Button(
                label="上一页", emoji="⬅️", style=discord.ButtonStyle.secondary
            )
            prev_btn.callback = self._prev_page_callback
            self.add_item(prev_btn)

        if self.current_page < self.total_pages - 1:
            next_btn = discord.ui.Button(
                label="下一页", emoji="➡️", style=discord.ButtonStyle.secondary
            )
            next_btn.callback = self._next_page_callback
            self.add_item(next_btn)

        # 确认清理按钮
        cleanup_btn = discord.ui.Button(
            label="确认清理全部",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
        )
        cleanup_btn.callback = self._cleanup_callback
        self.add_item(cleanup_btn)

        # 取消按钮
        cancel_btn = discord.ui.Button(
            label="取消", style=discord.ButtonStyle.secondary
        )
        cancel_btn.callback = self._cancel_callback
        self.add_item(cancel_btn)

    async def _prev_page_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "只有操作者可以控制此视图。", ephemeral=True
            )
        self.current_page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _next_page_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "只有操作者可以控制此视图。", ephemeral=True
            )
        self.current_page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _cleanup_callback(self, interaction: discord.Interaction):
        """执行清理操作"""
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "只有操作者可以执行此操作。", ephemeral=True
            )

        await interaction.response.edit_message(
            content="⏳ 正在清理失效帖子，请稍候...", embed=None, view=None
        )

        try:
            # 导入清理服务
            from src.chat.features.forum_search.cogs.forum_cleanup_cog import (
                forum_cleanup_cog,
            )

            if forum_cleanup_cog is None:
                if interaction.message:
                    await interaction.followup.edit_message(
                        interaction.message.id,
                        content="❌ 清理服务未初始化，请稍后重试。",
                    )
                return

            # 执行清理
            result = await forum_cleanup_cog.cleanup_all_channels()

            # 构建结果消息
            if result["total_deleted"] == 0:
                content = "✅ 清理完成！没有发现失效帖子。"
            else:
                channel_details = "\n".join(
                    [
                        f"• {ch['channel_name']}: 清理了 {ch['deleted']} 个"
                        for ch in result["channels"]
                        if ch["deleted"] > 0
                    ]
                )
                content = (
                    f"🧹 **清理完成！**\n\n"
                    f"**共清理 {result['total_deleted']} 个失效帖子**\n"
                    f"{channel_details}"
                )

            if interaction.message:
                await interaction.followup.edit_message(
                    interaction.message.id,
                    content=content,
                )

        except Exception as e:
            log.error(f"清理失效帖子时出错: {e}", exc_info=True)
            if interaction.message:
                await interaction.followup.edit_message(
                    interaction.message.id,
                    content=f"❌ 清理过程中发生错误: {e}",
                )

    async def _cancel_callback(self, interaction: discord.Interaction):
        """取消操作"""
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "只有操作者可以执行此操作。", ephemeral=True
            )
        await interaction.response.edit_message(
            content="已取消清理操作。", embed=None, view=None
        )

    def build_embed(self) -> discord.Embed:
        """构建当前页的 Embed"""
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.deleted_threads))
        page_items = self.deleted_threads[start_idx:end_idx]

        embed = discord.Embed(
            title=f"🔍 失效帖子列表 (共 {len(self.deleted_threads)} 个)",
            description="以下帖子在 Discord 上已被删除，但数据库中仍有记录：",
            color=discord.Color.orange(),
        )

        for i, thread in enumerate(page_items, start=start_idx + 1):
            thread_id = thread.get("thread_id", "N/A")
            thread_name = thread.get("thread_name", "未知标题")
            author_name = thread.get("author_name", "未知作者")
            channel_name = thread.get("channel_name", "未知频道")
            channel_id = thread.get("channel_id", 0)

            # 构建 Discord 帖子链接
            if self.guild_id:
                thread_link = f"https://discord.com/channels/{self.guild_id}/{channel_id}/{thread_id}"
                title_text = f"**{i}. [{thread_name[:30]}{'...' if len(thread_name) > 30 else ''}]({thread_link})**"
            else:
                title_text = f"**{i}. {thread_name[:30]}{'...' if len(thread_name) > 30 else ''}**"

            embed.add_field(
                name=title_text,
                value=f"作者: {author_name} | 频道: {channel_name}\nID: `{thread_id}`",
                inline=False,
            )

        embed.set_footer(
            text=f"第 {self.current_page + 1} / {self.total_pages} 页 | 点击标题可跳转到原帖子位置"
        )

        return embed
