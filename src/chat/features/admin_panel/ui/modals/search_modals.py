# -*- coding: utf-8 -*-
import discord
import logging
import sqlite3

from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)
from src.chat.features.admin_panel.services import db_services
from ..typing import AnyDBView
from .edit_modals import EditMemoryModal

log = logging.getLogger(__name__)


# --- 确认编辑记忆的视图 ---
class ConfirmEditMemoryView(discord.ui.View):
    def __init__(
        self,
        db_view: AnyDBView,
        user_id: int,
        member_name: str,
        memory_summary: str,
        author_id: int,
    ):
        super().__init__(timeout=180)
        self.db_view = db_view
        self.user_id = user_id
        self.member_name = member_name
        self.memory_summary = memory_summary
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the original author can interact."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "你不能操作这个按钮。", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="直接编辑记忆", style=discord.ButtonStyle.primary, emoji="🧠"
    )
    async def edit_memory(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Opens the EditMemoryModal."""
        modal = EditMemoryModal(
            self.db_view, self.user_id, self.member_name, self.memory_summary
        )
        await interaction.response.send_modal(modal)

        button.disabled = True
        button.label = "已打开编辑器"
        try:
            if interaction.message:
                await interaction.message.edit(view=self)
        except discord.errors.NotFound:
            log.info(
                "Could not edit ephemeral message after sending modal. This is expected."
            )
            pass

        self.stop()


# --- 搜索用户的模态窗口 ---
class SearchUserModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView):
        super().__init__(title="通过 Discord ID 搜索用户")
        self.db_view = db_view
        self.user_id_input = discord.ui.TextInput(
            label="输入用户的 Discord 数字 ID",
            placeholder="例如: 123456789012345678",
            required=True,
            min_length=17,
            max_length=20,
        )
        self.add_item(self.user_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id_str = self.user_id_input.value.strip()
        if not user_id_str.isdigit():
            await interaction.response.send_message(
                "请输入一个有效的数字ID。", ephemeral=True
            )
            return

        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        target_user_db_id = None
        target_index = -1
        try:
            cursor = db_services.get_cursor(conn)
            cursor.execute(
                "SELECT id, discord_id FROM community.member_profiles ORDER BY id DESC"
            )
            all_users = cursor.fetchall()
            for i, user in enumerate(all_users):
                if str(user["discord_id"]) == user_id_str:
                    target_index = i
                    target_user_db_id = user["id"]
                    break
        except sqlite3.Error as e:
            log.error(f"在 on_submit 中搜索用户时发生数据库错误: {e}", exc_info=True)
            await interaction.response.send_message(
                f"搜索时发生数据库错误: {e}", ephemeral=True
            )
            return
        finally:
            if conn:
                conn.close()

        # --- Case 1: 用户在社区成员档案中找到 ---
        if target_index != -1:
            await interaction.response.defer()
            page = target_index // self.db_view.items_per_page
            position_on_page = (target_index % self.db_view.items_per_page) + 1
            self.db_view.current_page = page
            await self.db_view.update_view()
            await interaction.followup.send(
                f"✅ 用户 `{user_id_str}` 已找到。\n"
                f"跳转到第 **{page + 1}** 页，其档案 `#{target_user_db_id}` 是该页的第 **{position_on_page}** 个。",
                ephemeral=True,
            )
        # --- Case 2: 未找到用户档案，检查个人记忆 ---
        else:
            try:
                user_id_int = int(user_id_str)
                memory_summary = await personal_memory_service.get_memory_summary(
                    user_id_int
                )
                # --- Case 2a: 找到个人记忆 ---
                if memory_summary is not None:
                    log.info(
                        f"未找到社区成员档案，但找到了用户 {user_id_str} 的个人记忆，直接打开编辑窗口。"
                    )
                    member_name = f"用户 {user_id_str}"
                    try:
                        if interaction.guild:
                            member = await interaction.guild.fetch_member(user_id_int)
                            member_name = member.display_name
                    except (discord.NotFound, discord.HTTPException):
                        pass  # 获取失败则使用默认名称

                    # --- 不能在 Modal on_submit 中再打开 Modal，所以发送一个带按钮的消息 ---
                    view = ConfirmEditMemoryView(
                        self.db_view,
                        user_id_int,
                        member_name,
                        memory_summary,
                        interaction.user.id,
                    )
                    await interaction.response.send_message(
                        f"ℹ️ 未找到用户 `{user_id_str}` 的社区档案，但检测到其个人记忆。",
                        view=view,
                        ephemeral=True,
                    )
                # --- Case 2b: 既无档案也无记忆 ---
                else:
                    await interaction.response.send_message(
                        f"❌ 未找到 Discord ID 为 `{user_id_str}` 的用户。",
                        ephemeral=True,
                    )
            except ValueError:
                await interaction.response.send_message(
                    f"❌ 无效的 Discord ID `{user_id_str}`。", ephemeral=True
                )
            except Exception as e:
                log.error(f"搜索用户时发生意外错误: {e}", exc_info=True)
                await interaction.response.send_message(
                    f"搜索时发生未知错误: {e}", ephemeral=True
                )


# --- 搜索社区知识的模态窗口 ---
class SearchKnowledgeModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView):
        super().__init__(title="搜索社区知识")
        self.db_view = db_view
        self.keyword_input = discord.ui.TextInput(
            label="输入搜索关键词",
            placeholder="搜索标题和内容...",
            required=True,
            max_length=100,
        )
        self.add_item(self.keyword_input)

    async def on_submit(self, interaction: discord.Interaction):
        keyword = self.keyword_input.value.strip()
        if not keyword:
            await interaction.response.send_message(
                "请输入有效的搜索关键词。", ephemeral=True
            )
            return

        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = db_services.get_cursor(conn)
            # 根据数据库类型选择正确的占位符
            placeholder = "?" if self.db_view.db_type == "sqlite" else "%s"

            # 搜索标题和内容字段，使用LIKE进行模糊匹配
            if self.db_view.db_type == "parade":
                # PostgreSQL/ParadeDB 查询
                cursor.execute(
                    f"""
                    SELECT id, title, full_text FROM general_knowledge.knowledge_documents
                    WHERE title LIKE {placeholder} OR full_text LIKE {placeholder}
                    ORDER BY created_at DESC, id DESC
                    """,
                    (f"%{keyword}%", f"%{keyword}%"),
                )
            else:
                # SQLite 查询（旧表结构）
                cursor.execute(
                    f"""
                    SELECT id, title, content_json FROM general_knowledge
                    WHERE title LIKE {placeholder} OR content_json LIKE {placeholder}
                    ORDER BY created_at DESC, id DESC
                    """,
                    (f"%{keyword}%", f"%{keyword}%"),
                )

            results = cursor.fetchall()

            if not results:
                await interaction.response.send_message(
                    f"❌ 未找到包含关键词 `{keyword}` 的社区知识。", ephemeral=True
                )
                return

            # 将 DictRow 转换为字典
            dict_results = [dict(row) for row in results]

            # 将搜索结果设置为当前列表项，并跳转到第一页
            self.db_view.current_list_items = dict_results
            self.db_view.current_page = 0
            self.db_view.total_pages = (
                len(results) + self.db_view.items_per_page - 1
            ) // self.db_view.items_per_page
            self.db_view.search_mode = True
            self.db_view.search_keyword = keyword

            await interaction.response.defer()
            await self.db_view.update_view()
            await interaction.followup.send(
                f"✅ 找到 {len(results)} 条包含关键词 `{keyword}` 的社区知识。",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"搜索社区知识时发生数据库错误: {e}", exc_info=True)
            await interaction.response.send_message(
                f"搜索时发生数据库错误: {e}", ephemeral=True
            )
        finally:
            if conn:
                conn.close()


# --- 新增：搜索工作事件的模态窗口 ---
class SearchWorkEventModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView):
        super().__init__(title="搜索工作事件")
        self.db_view = db_view
        self.keyword_input = discord.ui.TextInput(
            label="输入搜索关键词",
            placeholder="搜索名称和描述...",
            required=True,
            max_length=100,
        )
        self.add_item(self.keyword_input)

    async def on_submit(self, interaction: discord.Interaction):
        keyword = self.keyword_input.value.strip()
        if not keyword:
            await interaction.response.send_message(
                "请输入有效的搜索关键词。", ephemeral=True
            )
            return

        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM work_events
                WHERE name LIKE ? OR description LIKE ?
                ORDER BY id DESC
                """,
                (f"%{keyword}%", f"%{keyword}%"),
            )
            results = cursor.fetchall()

            if not results:
                await interaction.response.send_message(
                    f"❌ 未找到包含关键词 `{keyword}` 的工作事件。", ephemeral=True
                )
                return

            self.db_view.current_list_items = results
            self.db_view.current_page = 0
            self.db_view.total_pages = (
                len(results) + self.db_view.items_per_page - 1
            ) // self.db_view.items_per_page
            self.db_view.search_mode = True
            self.db_view.search_keyword = keyword

            await interaction.response.defer()
            await self.db_view.update_view()
            await interaction.followup.send(
                f"✅ 找到 {len(results)} 条包含关键词 `{keyword}` 的工作事件。",
                ephemeral=True,
            )

        except sqlite3.Error as e:
            log.error(f"搜索工作事件时发生数据库错误: {e}", exc_info=True)
            await interaction.response.send_message(
                f"搜索时发生数据库错误: {e}", ephemeral=True
            )
        finally:
            if conn:
                conn.close()


# --- 新增：搜索社区成员的模态窗口 ---
class SearchCommunityMemberModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView):
        super().__init__(title="搜索社区成员")
        self.db_view = db_view
        self.keyword_input = discord.ui.TextInput(
            label="输入搜索关键词",
            placeholder="搜索标题和内容...",
            required=True,
            max_length=100,
        )
        self.add_item(self.keyword_input)

    async def on_submit(self, interaction: discord.Interaction):
        keyword = self.keyword_input.value.strip()
        if not keyword:
            await interaction.response.send_message(
                "请输入有效的搜索关键词。", ephemeral=True
            )
            return

        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = db_services.get_cursor(conn)
            # 根据数据库类型选择正确的占位符
            placeholder = "?" if self.db_view.db_type == "sqlite" else "%s"

            # 搜索 title 和 content_json 字段
            # 注意：表名已从 community_members 改为 community.member_profiles
            # 并且字段名可能已更改，需要根据实际表结构调整
            if self.db_view.db_type == "parade":
                # PostgreSQL/ParadeDB 查询
                cursor.execute(
                    f"""
                    SELECT * FROM community.member_profiles
                    WHERE title LIKE {placeholder} OR full_text LIKE {placeholder}
                    ORDER BY id DESC
                    """,
                    (f"%{keyword}%", f"%{keyword}%"),
                )
            else:
                # SQLite 查询（旧表结构）
                cursor.execute(
                    f"""
                    SELECT * FROM community.member_profiles
                    WHERE title LIKE {placeholder} OR content_json LIKE {placeholder}
                    ORDER BY id DESC
                    """,
                    (f"%{keyword}%", f"%{keyword}%"),
                )

            results = cursor.fetchall()

            if not results:
                await interaction.response.send_message(
                    f"❌ 未找到包含关键词 `{keyword}` 的社区成员档案。", ephemeral=True
                )
                return

            # 将 DictRow 转换为字典
            dict_results = [dict(row) for row in results]
            self.db_view.current_list_items = dict_results
            self.db_view.current_page = 0
            self.db_view.total_pages = (
                len(results) + self.db_view.items_per_page - 1
            ) // self.db_view.items_per_page
            self.db_view.search_mode = True
            self.db_view.search_keyword = keyword

            await interaction.response.defer()
            await self.db_view.update_view()
            await interaction.followup.send(
                f"✅ 找到 {len(results)} 条包含关键词 `{keyword}` 的社区成员档案。",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"搜索社区成员时发生数据库错误: {e}", exc_info=True)
            await interaction.response.send_message(
                f"搜索时发生数据库错误: {e}", ephemeral=True
            )
        finally:
            if conn:
                conn.close()


# --- 新增：搜索向量数据库的模态窗口 ---
class SearchVectorDBModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView):
        super().__init__(title="搜索向量数据库 (帖子)")
        self.db_view = db_view
        self.keyword_input = discord.ui.TextInput(
            label="输入元数据搜索关键词",
            placeholder="在帖子标题等元数据中搜索...",
            required=True,
            max_length=100,
        )
        self.add_item(self.keyword_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        keyword = self.keyword_input.value.strip()
        if not keyword:
            await interaction.followup.send("请输入有效的搜索关键词。", ephemeral=True)
            return

        try:
            if (
                not forum_vector_db_service
                or not forum_vector_db_service.is_available()
            ):
                raise ConnectionError("未能连接到向量数据库服务。")

            # 使用 forum_search_service 进行搜索（语义搜索 + 元数据过滤）
            from src.chat.features.forum_search.services.forum_search_service import (
                forum_search_service,
            )

            if not forum_search_service.is_ready():
                await interaction.followup.send(
                    "论坛搜索服务未就绪，请稍后再试。", ephemeral=True
                )
                return

            # 执行搜索
            results = await forum_search_service.search(
                query=keyword,
                n_results=100,  # 获取更多结果用于浏览
                filters=None,
            )

            if not results:
                await interaction.followup.send(
                    f"❌ 未找到包含 `{keyword}` 的帖子。", ephemeral=True
                )
                return

            self.db_view.current_list_items = results
            self.db_view.current_page = 0
            self.db_view.total_pages = (
                len(results) + self.db_view.items_per_page - 1
            ) // self.db_view.items_per_page
            self.db_view.search_mode = True
            self.db_view.search_keyword = keyword

            await self.db_view.update_view()
            await interaction.followup.send(
                f"✅ 找到 {len(results)} 条包含 `{keyword}` 的帖子。",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"搜索向量数据库时发生错误: {e}", exc_info=True)
            await interaction.followup.send(f"搜索时发生错误: {e}", ephemeral=True)
