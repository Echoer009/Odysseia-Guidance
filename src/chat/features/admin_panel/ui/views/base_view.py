# -*- coding: utf-8 -*-

import discord
import logging
import os
import sqlite3
from typing import List, Optional, Any, cast, Mapping, Union
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import config
from src.chat.features.admin_panel.services import db_services
from src.chat.features.admin_panel.ui.modals.utility_modals import JumpToPageModal
from src.chat.features.world_book.services.incremental_rag_service import (
    incremental_rag_service,
)
from src.chat.utils.database import DB_PATH as CHAT_DB_PATH, get_database_url
from src.database.models import CommunityMemberProfile, GeneralKnowledgeDocument

log = logging.getLogger(__name__)

# 表名到 SQLAlchemy 模型的映射
TABLE_TO_MODEL_MAP = {
    "community.member_profiles": CommunityMemberProfile,
    "general_knowledge.knowledge_documents": GeneralKnowledgeDocument,
}


class BaseTableView(discord.ui.View):
    """所有表格视图的基类，包含通用功能。"""

    def __init__(self, author_id: int, message: discord.Message, parent_view: Any):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.message = message
        self.parent_view = parent_view
        self.world_book_db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")
        self.chat_db_path = CHAT_DB_PATH

        # --- 状态管理 ---
        self.current_table: Optional[str] = None
        self.db_type: str = "sqlite"  # 默认 'sqlite', 可被子类覆盖
        self.view_mode: str = "list"
        self.current_page: int = 0
        self.items_per_page: int = 10
        self.total_pages: int = 0
        self.current_item_id: Optional[str] = None
        self.current_list_items: List[Any] = []  # 改为 Any 以兼容不同数据库行类型
        self.search_mode: bool = False
        self.search_keyword: Optional[str] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "你不能操作这个视图。", ephemeral=True
            )
            return False
        return True

    def _get_db_connection(self) -> Optional[Union[sqlite3.Connection, Any]]:
        db_path = (
            self.chat_db_path
            if self.current_table == "work_events"
            else self.world_book_db_path
        )
        return db_services.get_db_connection(self.db_type, db_path=db_path)

    def _get_primary_key_column(self) -> str:
        return "id"  # 默认为 'id'，子类可以重写

    def _initialize_components(self):
        self.clear_items()

        # 返回主菜单按钮
        back_button = discord.ui.Button(
            label="返回主菜单", emoji="⬅️", style=discord.ButtonStyle.secondary, row=4
        )
        back_button.callback = self.go_to_main_menu
        self.add_item(back_button)

        if self.view_mode == "list":
            self._add_list_view_components()
        elif self.view_mode == "detail":
            self._add_detail_view_components()

    def _add_list_view_components(self):
        # 分页按钮
        self.prev_button = discord.ui.Button(
            label="上一页",
            emoji="⬅️",
            style=discord.ButtonStyle.secondary,
            disabled=self.current_page == 0,
        )
        self.prev_button.callback = self.go_to_previous_page
        self.add_item(self.prev_button)

        self.next_button = discord.ui.Button(
            label="下一页",
            emoji="➡️",
            style=discord.ButtonStyle.secondary,
            disabled=self.current_page >= self.total_pages - 1,
        )
        self.next_button.callback = self.go_to_next_page
        self.add_item(self.next_button)

        self.jump_button = discord.ui.Button(
            label="跳转",
            emoji="🔢",
            style=discord.ButtonStyle.secondary,
            disabled=self.total_pages <= 1,
        )
        self.jump_button.callback = self.jump_to_page
        self.add_item(self.jump_button)

        # 搜索按钮（由子类添加）
        self._add_search_buttons()

        if self.search_mode:
            self.exit_search_button = discord.ui.Button(
                label="退出搜索",
                emoji="❌",
                style=discord.ButtonStyle.secondary,
                row=1,
            )
            self.exit_search_button.callback = self.exit_search
            self.add_item(self.exit_search_button)

        # 列表选择菜单
        if self.current_list_items:
            items_for_select = self.current_list_items
            if self.search_mode:
                start_idx = self.current_page * self.items_per_page
                end_idx = start_idx + self.items_per_page
                items_for_select = self.current_list_items[start_idx:end_idx]

            if items_for_select:
                self.add_item(self._create_item_select(items_for_select))

    def _add_detail_view_components(self):
        self.back_button = discord.ui.Button(
            label="返回列表", emoji="⬅️", style=discord.ButtonStyle.secondary
        )
        self.back_button.callback = self.go_to_list_view
        self.add_item(self.back_button)

        self.edit_button = discord.ui.Button(
            label="修改", emoji="✏️", style=discord.ButtonStyle.primary
        )
        self.edit_button.callback = self.edit_item
        self.add_item(self.edit_button)

        self.delete_button = discord.ui.Button(
            label="删除", emoji="🗑️", style=discord.ButtonStyle.danger
        )
        self.delete_button.callback = self.delete_item
        self.add_item(self.delete_button)

    def _add_search_buttons(self):
        # 子类将在这里实现并添加特定的搜索按钮
        pass

    def _create_item_select(self, items_to_display: List) -> discord.ui.Select:
        options = []
        pk = self._get_primary_key_column()
        for item in items_to_display:
            title = self._get_entry_title(dict(item))
            item_id = item[pk]
            label = f"#{item_id}. {title}"
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(discord.SelectOption(label=label, value=str(item_id)))

        select = discord.ui.Select(
            placeholder="选择一个条目查看详情...", options=options
        )
        select.callback = self.on_item_select
        return select

    # --- 交互处理 ---

    async def go_to_main_menu(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.parent_view.update_view()

    async def on_item_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if interaction.data and isinstance(interaction.data, dict):
            values = cast(list, interaction.data.get("values", []))
            if values:
                self.current_item_id = values[0]
        self.view_mode = "detail"
        await self.update_view()

    async def go_to_list_view(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view_mode = "list"
        self.current_item_id = None
        await self.update_view()

    async def go_to_previous_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_view()

    async def go_to_next_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_view()

    async def jump_to_page(self, interaction: discord.Interaction):
        if self.total_pages > 1:
            modal = JumpToPageModal(self)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(
                "只有一页，无需跳转。", ephemeral=True
            )

    async def exit_search(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.search_mode = False
        self.search_keyword = None
        self.current_page = 0
        await self.update_view()

    async def edit_item(self, interaction: discord.Interaction):
        # 子类将实现此方法以打开特定的编辑模态窗口
        raise NotImplementedError

    async def delete_item(self, interaction: discord.Interaction):
        if not self.current_item_id:
            return await interaction.response.send_message(
                "没有可删除的条目。", ephemeral=True
            )
        item_id = self.current_item_id

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            if not self.current_table:
                log.error("delete_item called without a current_table defined.")
                await interaction.response.edit_message(
                    content="错误：未指定要操作的表。", view=None
                )
                return

            model_class = TABLE_TO_MODEL_MAP.get(self.current_table)

            if not model_class:
                log.warning(
                    f"删除操作被阻止，因为表 '{self.current_table}' 没有在ORM删除映射中定义。"
                )
                await interaction.response.edit_message(
                    content=f"错误：表 `{self.current_table}` 不支持ORM删除操作。",
                    view=None,
                )
                return

            # --- 通用ORM删除逻辑 ---
            DATABASE_URL = get_database_url(sync=True)
            engine = create_engine(DATABASE_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            session = SessionLocal()
            try:
                item_to_delete = session.get(model_class, int(item_id))
                if item_to_delete:
                    session.delete(item_to_delete)
                    session.commit()
                    log.info(
                        f"管理员 {interaction.user.display_name} 删除了表 '{self.current_table}' 的记录 ID {item_id} (ORM Path)。"
                    )

                    # --- 重新加入向量删除逻辑 ---
                    try:
                        await incremental_rag_service.delete_entry(item_id)
                        log.info(f"条目 {item_id} 的关联向量已从 RAG 中删除。")
                    except Exception as e:
                        log.error(
                            f"删除条目 {item_id} 的向量时出错: {e}", exc_info=True
                        )
                        # 注意：即使向量删除失败，主记录也已删除，这里只记录错误。

                    await interaction.response.edit_message(
                        content=f"🗑️ 记录 `#{item_id}` 已被成功删除。", view=None
                    )
                    self.view_mode = "list"
                    await self.update_view()
                else:
                    await interaction.response.edit_message(
                        content=f"错误：在表 `{self.current_table}` 中找不到ID为 {item_id} 的记录。",
                        view=None,
                    )
            except Exception as e:
                session.rollback()
                log.error(f"ORM删除记录失败: {e}", exc_info=True)
                await interaction.response.edit_message(
                    content=f"删除失败: {e}", view=None
                )
            finally:
                session.close()

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
            f"**⚠️ 确认删除**\n你确定要永久删除表 `{self.current_table}` 中 ID 为 `#{item_id}` 的记录吗？此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
        )

    # --- 视图/Embed 更新 ---

    async def update_view(self):
        if not self.message:
            log.warning("尝试更新视图，但没有关联的 message 对象。")
            return

        if self.view_mode == "list":
            embed = await self._build_list_embed()
        else:
            embed = await self._build_detail_embed()

        self._initialize_components()

        try:
            await self.message.edit(embed=embed, view=self)
        except discord.errors.NotFound:
            log.warning("尝试编辑消息失败，消息可能已被删除。")

    def _get_entry_title(self, entry: Mapping[str, Any]) -> str:
        # 子类将重写此方法以提供更具描述性的标题
        pk = self._get_primary_key_column()
        try:
            # sqlite3.Row can be accessed by key
            return f"ID: #{entry[pk]}"
        except IndexError:
            # Fallback if the primary key is not found
            return f"ID: #{entry['id']}"

    def _truncate_field_value(self, value: Any) -> str:
        value_str = str(value)
        if len(value_str) > 1024:
            return value_str[:1021] + "..."
        return value_str

    async def _build_list_embed(self) -> discord.Embed:
        # 子类将实现此方法以构建其特定的列表 embed
        raise NotImplementedError

    async def _build_detail_embed(self) -> discord.Embed:
        # 子类将实现此方法以构建其特定的详情 embed
        raise NotImplementedError
