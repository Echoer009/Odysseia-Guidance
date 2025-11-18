# -*- coding: utf-8 -*-

import discord
import logging
import sqlite3
import os
import json
from typing import List, Optional

from src import config
from src.chat.features.world_book.services.incremental_rag_service import (
    incremental_rag_service,
)
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)
from src.chat.features.admin_panel.ui.coin_management_view import CoinManagementView
from src.chat.utils.database import DB_PATH as CHAT_DB_PATH
from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.config import chat_config
from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)
import asyncio

log = logging.getLogger(__name__)


# --- 新增：编辑个人记忆的模态窗口 ---
class EditMemoryModal(discord.ui.Modal):
    def __init__(
        self, db_view: "DBView", user_id: int, member_name: str, current_summary: str
    ):
        super().__init__(title=f"编辑 {member_name} 的记忆")
        self.db_view = db_view
        self.user_id = user_id

        self.summary_input = discord.ui.TextInput(
            label="个人记忆摘要",
            style=discord.TextStyle.paragraph,
            default=current_summary,
            max_length=4000,  # Discord TextInput 最大长度
            required=False,
        )
        self.add_item(self.summary_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_summary = self.summary_input.value.strip()

        try:
            await personal_memory_service.update_memory_summary(
                self.user_id, new_summary
            )
            log.info(
                f"管理员 {interaction.user.display_name} 更新了用户 {self.user_id} 的记忆摘要。"
            )
            await interaction.followup.send(
                f"✅ 用户 `{self.user_id}` 的记忆摘要已成功更新。", ephemeral=True
            )
        except Exception as e:
            log.error(f"更新用户 {self.user_id} 的记忆时出错: {e}", exc_info=True)
            await interaction.followup.send(f"更新记忆时发生错误: {e}", ephemeral=True)


# --- 确认编辑记忆的视图 ---
class ConfirmEditMemoryView(discord.ui.View):
    def __init__(
        self,
        db_view: "DBView",
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

        # Disable the button for better UX.
        button.disabled = True
        button.label = "已打开编辑器"
        try:
            # Attempt to edit the original message to show the disabled button.
            # This may fail for ephemeral messages, which is an expected behavior.
            await interaction.message.edit(view=self)
        except discord.errors.NotFound:
            # The original ephemeral message could not be found, which is fine.
            # The modal was sent successfully. We'll log this for debugging.
            log.info(
                "Could not edit ephemeral message after sending modal. This is expected."
            )
            pass

        self.stop()


# --- 编辑社区成员的模态窗口 ---
class EditCommunityMemberModal(discord.ui.Modal):
    def __init__(self, db_view: "DBView", item_id: str, current_data: sqlite3.Row):
        modal_title = f"编辑社区成员档案 #{item_id}"
        if len(modal_title) > 45:
            modal_title = modal_title[:42] + "..."
        super().__init__(title=modal_title)
        self.db_view = db_view
        self.item_id = item_id
        self.current_data = dict(current_data) if current_data else {}

        # --- 从 content_json 中解析数据 ---
        content_data = {}
        if "content_json" in self.current_data:
            try:
                content_data = json.loads(self.current_data["content_json"])
            except (json.JSONDecodeError, TypeError):
                log.warning(
                    f"无法解析 community_members #{self.item_id} 的 content_json。"
                )

        # 成员名称
        self.add_item(
            discord.ui.TextInput(
                label="成员名称 (name)",
                default=content_data.get("name", ""),
                max_length=100,
                required=True,
            )
        )
        # Discord ID
        self.add_item(
            discord.ui.TextInput(
                label="Discord ID (discord_number_id)",
                default=str(self.current_data.get("discord_number_id", "")),
                max_length=20,
                required=True,
            )
        )
        # 性格特点
        self.add_item(
            discord.ui.TextInput(
                label="性格特点 (personality)",
                default=content_data.get("personality", ""),
                style=discord.TextStyle.paragraph,
                max_length=500,
                required=True,
            )
        )
        # 背景信息
        self.add_item(
            discord.ui.TextInput(
                label="背景信息 (background)",
                default=content_data.get("background", ""),
                style=discord.TextStyle.paragraph,
                max_length=1000,
                required=False,
            )
        )
        # 喜好偏好
        self.add_item(
            discord.ui.TextInput(
                label="喜好偏好 (preferences)",
                default=content_data.get("preferences", ""),
                style=discord.TextStyle.paragraph,
                max_length=500,
                required=False,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = conn.cursor()

            # 从模态窗口的子组件中获取更新后的值
            updated_name = self.children[0].value.strip()
            updated_discord_id = self.children[1].value.strip()

            # 更新 content_json 的内容
            new_content_data = {
                "name": updated_name,
                "discord_id": updated_discord_id,
                "personality": self.children[2].value.strip(),
                "background": self.children[3].value.strip(),
                "preferences": self.children[4].value.strip(),
            }
            content_json = json.dumps(new_content_data, ensure_ascii=False)

            # 构建 SQL 更新语句
            sql = """
                UPDATE community_members
                SET title = ?, discord_number_id = ?, content_json = ?
                WHERE id = ?
            """
            params = (
                f"社区成员档案 - {updated_name}",
                updated_discord_id,
                content_json,
                self.item_id,
            )

            cursor.execute(sql, params)
            conn.commit()
            log.info(
                f"管理员 {interaction.user.display_name} 成功更新了表 'community_members' 中 ID 为 {self.item_id} 的记录。"
            )

            await interaction.response.send_message(
                f"✅ 社区成员档案 `#{self.item_id}` 已成功更新。", ephemeral=True
            )

            # --- RAG 更新 ---
            log.info(f"开始为更新后的社区成员 {self.item_id} 同步向量数据库...")
            # 1. 删除旧的向量
            await incremental_rag_service.delete_entry(self.item_id)
            # 2. 为新数据创建向量
            await incremental_rag_service.process_community_member(self.item_id)
            log.info(f"社区成员 {self.item_id} 的向量数据库同步完成。")

            await self.db_view.update_view()

        except sqlite3.Error as e:
            log.error(f"更新社区成员档案失败: {e}", exc_info=True)
            await interaction.response.send_message(f"更新失败: {e}", ephemeral=True)
        finally:
            conn.close()


# --- 编辑工作事件的模态窗口 (已更新为倍率模型) ---
class EditWorkEventModal(discord.ui.Modal):
    def __init__(self, db_view: "DBView", item_id: str, current_data: sqlite3.Row):
        super().__init__(title=f"编辑工作事件 #{item_id}")
        self.db_view = db_view
        self.item_id = item_id
        self.current_data = dict(current_data)

        # 1. 事件名称
        self.add_item(
            discord.ui.TextInput(
                label="事件名称",
                default=self.current_data.get("name", ""),
                required=True,
            )
        )
        # 2. 事件描述
        self.add_item(
            discord.ui.TextInput(
                label="事件描述",
                default=self.current_data.get("description", ""),
                style=discord.TextStyle.paragraph,
                required=True,
            )
        )
        # 3. 基础奖励范围
        self.add_item(
            discord.ui.TextInput(
                label="基础奖励范围 (最小,最大)",
                placeholder="例如: 200,500",
                default=f"{self.current_data.get('reward_range_min', '')},{self.current_data.get('reward_range_max', '')}",
                required=True,
            )
        )
        # 4. 好事
        self.add_item(
            discord.ui.TextInput(
                label="好事: 描述 # 倍率 (可选)",
                placeholder="例如: 客人很满意 # 1.5",
                default=(
                    f"{self.current_data.get('good_event_description', '')} # {self.current_data.get('good_event_modifier', '')}"
                    if self.current_data.get("good_event_description")
                    else ""
                ),
                required=False,
                style=discord.TextStyle.paragraph,
            )
        )
        # 5. 坏事
        self.add_item(
            discord.ui.TextInput(
                label="坏事: 描述 # 倍率 (可选)",
                placeholder="例如: 被警察查房 # -0.5",
                default=(
                    f"{self.current_data.get('bad_event_description', '')} # {self.current_data.get('bad_event_modifier', '')}"
                    if self.current_data.get("bad_event_description")
                    else ""
                ),
                required=False,
                style=discord.TextStyle.paragraph,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = conn.cursor()

            # --- 解析字段 ---
            # 解析奖励范围
            try:
                reward_min_str, reward_max_str = (
                    self.children[2].value.strip().split(",")
                )
                reward_range_min = int(reward_min_str)
                reward_range_max = int(reward_max_str)
            except (ValueError, IndexError):
                await interaction.response.send_message(
                    "❌ 格式错误：基础奖励范围应为 `最小,最大`，例如 `200,500`。",
                    ephemeral=True,
                )
                return

            # 解析好事
            good_event_str = self.children[3].value.strip()
            good_event_description = None
            good_event_modifier = None
            if good_event_str:
                parts = good_event_str.split("#")
                if len(parts) == 2:
                    good_event_description = parts[0].strip()
                    try:
                        good_event_modifier = float(parts[1].strip())
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ 格式错误：好事倍率必须是数字。", ephemeral=True
                        )
                        return
                else:
                    await interaction.response.send_message(
                        "❌ 格式错误：好事应为 `描述 # 倍率`。", ephemeral=True
                    )
                    return

            # 解析坏事
            bad_event_str = self.children[4].value.strip()
            bad_event_description = None
            bad_event_modifier = None
            if bad_event_str:
                parts = bad_event_str.split("#")
                if len(parts) == 2:
                    bad_event_description = parts[0].strip()
                    try:
                        bad_event_modifier = float(parts[1].strip())
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ 格式错误：坏事倍率必须是数字。", ephemeral=True
                        )
                        return
                else:
                    await interaction.response.send_message(
                        "❌ 格式错误：坏事应为 `描述 # 倍率`。", ephemeral=True
                    )
                    return

            # 构建 SQL 更新语句
            sql = """
                UPDATE work_events
                SET name = ?, description = ?, reward_range_min = ?, reward_range_max = ?,
                    good_event_description = ?, good_event_modifier = ?,
                    bad_event_description = ?, bad_event_modifier = ?
                WHERE event_id = ?
            """
            params = (
                self.children[0].value.strip(),  # name
                self.children[1].value.strip(),  # description
                reward_range_min,
                reward_range_max,
                good_event_description,
                good_event_modifier,
                bad_event_description,
                bad_event_modifier,
                self.item_id,
            )

            cursor.execute(sql, params)
            conn.commit()
            log.info(
                f"管理员 {interaction.user.display_name} 成功更新了表 'work_events' 中 ID 为 {self.item_id} 的记录。"
            )

            await interaction.response.send_message(
                f"✅ 工作事件 `#{self.item_id}` 已成功更新。", ephemeral=True
            )
            await self.db_view.update_view()

        except sqlite3.Error as e:
            log.error(f"更新工作事件失败: {e}", exc_info=True)
            await interaction.response.send_message(f"更新失败: {e}", ephemeral=True)
        except Exception as e:
            log.error(f"解析工作事件字段时发生未知错误: {e}", exc_info=True)
            await interaction.response.send_message(
                f"处理输入时发生错误: {e}", ephemeral=True
            )
        finally:
            if conn:
                conn.close()


# --- 编辑条目的模态窗口 ---
class EditModal(discord.ui.Modal):
    def __init__(
        self,
        db_view: "DBView",
        table_name: str,
        item_id: str,
        current_data: sqlite3.Row,
    ):
        # 构造并截断标题以防止超长
        self.db_view = db_view  # 修正: 将传入的 db_view 实例赋值给 self
        raw_title = self.db_view._get_entry_title(current_data)
        truncated_title = (raw_title[:30] + "...") if len(raw_title) > 30 else raw_title
        modal_title = f"编辑: {truncated_title} (#{item_id})"
        if len(modal_title) > 45:
            modal_title = modal_title[:42] + "..."

        super().__init__(title=modal_title)
        self.db_view = db_view
        self.table_name = table_name
        self.item_id = item_id
        self.current_data = current_data

        # 获取除 'id' 外的所有列
        columns = [col for col in self.current_data.keys() if col.lower() != "id"]

        # Discord 模态窗口最多支持5个组件
        if len(columns) > 4:
            # 这里的 self.title 赋值也会影响最终标题，所以也要截断
            base_title = f"编辑: {truncated_title} (#{item_id})"
            suffix = " (前4字段)"
            if len(base_title) + len(suffix) > 45:
                allowed_len = 45 - len(suffix) - 3  # 3 for "..."
                base_title = base_title[:allowed_len] + "..."
            self.title = base_title + suffix
            columns_to_display = columns[:4]
        else:
            columns_to_display = columns

        # 动态添加文本输入框
        for col in columns_to_display:
            value = self.current_data[col]
            # 对于 JSON 字段，美化后放入编辑框
            if isinstance(value, str) and (
                value.startswith("{") or value.startswith("[")
            ):
                try:
                    parsed_json = json.loads(value)
                    value = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                    style = discord.TextStyle.paragraph
                except json.JSONDecodeError:
                    style = discord.TextStyle.short
            # 根据内容长度决定输入框样式
            elif isinstance(value, str) and len(value) > 100:
                style = discord.TextStyle.paragraph
            else:
                style = discord.TextStyle.short

            self.add_item(
                discord.ui.TextInput(
                    label=col,
                    default=str(value) if value is not None else "",
                    style=style,
                    required=False,  # 允许字段为空
                )
            )

    async def on_submit(self, interaction: discord.Interaction):
        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = conn.cursor()
            update_fields = []
            update_values = []

            # 从模态窗口的子组件中获取更新后的值
            for component in self.children:
                if isinstance(component, discord.ui.TextInput):
                    update_fields.append(f"{component.label} = ?")
                    update_values.append(component.value)

            update_values.append(self.item_id)

            # 构建并执行 SQL 更新语句
            sql = (
                f"UPDATE {self.table_name} SET {', '.join(update_fields)} WHERE id = ?"
            )
            cursor.execute(sql, tuple(update_values))
            conn.commit()
            log.info(
                f"管理员 {interaction.user.display_name} 成功更新了表 '{self.table_name}' 中 ID 为 {self.item_id} 的记录。"
            )

            await interaction.response.send_message(
                f"✅ 记录 `#{self.item_id}` 已成功更新。", ephemeral=True
            )

            # --- RAG 更新 (通用) ---
            log.info(
                f"开始为更新后的条目 {self.item_id} (表: {self.table_name}) 同步向量数据库..."
            )
            await incremental_rag_service.delete_entry(self.item_id)

            # 根据表名选择合适的处理函数
            if self.table_name == "community_members":
                await incremental_rag_service.process_community_member(self.item_id)
            elif self.table_name == "general_knowledge":
                await incremental_rag_service.process_general_knowledge(self.item_id)
            # 'pending_entries' 通常不直接进入 RAG，所以这里不处理

            log.info(f"条目 {self.item_id} 的向量数据库同步完成。")

            # 刷新原始的数据库浏览器视图
            await self.db_view.update_view()

        except sqlite3.Error as e:
            log.info(
                f"管理员 {interaction.user.display_name} 成功更新了表 '{self.table_name}' 中 ID 为 {self.item_id} 的记录。"
            )
            log.error(f"更新数据库记录失败: {e}", exc_info=True)
            await interaction.response.send_message(f"更新失败: {e}", ephemeral=True)
        finally:
            conn.close()


# --- 跳转页面的模态窗口 ---
class JumpToPageModal(discord.ui.Modal):
    def __init__(self, db_view: "DBView"):
        super().__init__(title="跳转到页面")
        self.db_view = db_view
        self.page_input = discord.ui.TextInput(
            label=f"输入页码 (1 - {self.db_view.total_pages})",
            placeholder="例如: 5",
            required=True,
            min_length=1,
            max_length=len(str(self.db_view.total_pages)),
        )
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        page_str = self.page_input.value
        if not page_str.isdigit():
            await interaction.followup.send("请输入一个有效的数字。", ephemeral=True)
            return

        page = int(page_str)
        if 1 <= page <= self.db_view.total_pages:
            self.db_view.current_page = page - 1
            await self.db_view.update_view()
        else:
            await interaction.followup.send(
                f"页码必须在 1 到 {self.db_view.total_pages} 之间。", ephemeral=True
            )


# --- 搜索用户的模态窗口 ---
class SearchUserModal(discord.ui.Modal):
    def __init__(self, db_view: "DBView"):
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
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, discord_number_id FROM community_members ORDER BY id DESC"
            )
            all_users = cursor.fetchall()
            for i, user in enumerate(all_users):
                if str(user["discord_number_id"]) == user_id_str:
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
    def __init__(self, db_view: "DBView"):
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
            cursor = conn.cursor()
            # 搜索标题和内容字段，使用LIKE进行模糊匹配
            cursor.execute(
                """
                SELECT id, title, content_json FROM general_knowledge
                WHERE title LIKE ? OR content_json LIKE ?
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

            # 将搜索结果设置为当前列表项，并跳转到第一页
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
                f"✅ 找到 {len(results)} 条包含关键词 `{keyword}` 的社区知识。",
                ephemeral=True,
            )

        except sqlite3.Error as e:
            log.error(f"搜索社区知识时发生数据库错误: {e}", exc_info=True)
            await interaction.response.send_message(
                f"搜索时发生数据库错误: {e}", ephemeral=True
            )
        finally:
            if conn:
                conn.close()


# --- 新增：搜索工作事件的模态窗口 ---
class SearchWorkEventModal(discord.ui.Modal):
    def __init__(self, db_view: "DBView"):
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
    def __init__(self, db_view: "DBView"):
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
            cursor = conn.cursor()
            # 搜索 title 和 content_json 字段
            cursor.execute(
                """
                SELECT * FROM community_members
                WHERE title LIKE ? OR content_json LIKE ?
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
                f"✅ 找到 {len(results)} 条包含关键词 `{keyword}` 的社区成员档案。",
                ephemeral=True,
            )

        except sqlite3.Error as e:
            log.error(f"搜索社区成员时发生数据库错误: {e}", exc_info=True)
            await interaction.response.send_message(
                f"搜索时发生数据库错误: {e}", ephemeral=True
            )
        finally:
            if conn:
                conn.close()


# --- 新增：搜索向量数据库的模态窗口 ---
class SearchVectorDBModal(discord.ui.Modal):
    def __init__(self, db_view: "DBView"):
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
            if not forum_vector_db_service or not forum_vector_db_service.client:
                raise ConnectionError("未能连接到向量数据库服务。")

            collection = forum_vector_db_service.client.get_collection(
                name=forum_vector_db_service.collection_name
            )

            # 性能优化：ChromaDB 不支持模糊搜索，我们先只获取元数据进行过滤
            all_items = collection.get(include=["metadatas"])

            if not all_items or not all_items["ids"]:
                await interaction.followup.send(
                    "❌ 向量数据库中没有任何帖子。", ephemeral=True
                )
                return

            # 在 Python 中对元数据进行不区分大小写的“包含”过滤
            keyword_lower = keyword.lower()
            matching_ids = []
            for i, metadata in enumerate(all_items["metadatas"]):
                thread_name = metadata.get("thread_name", "").lower()
                if keyword_lower in thread_name:
                    matching_ids.append(all_items["ids"][i])

            if not matching_ids:
                await interaction.followup.send(
                    f"❌ 未在元数据中找到包含 `{keyword}` 的帖子。", ephemeral=True
                )
                return

            # 仅获取匹配到的条目的完整数据
            results = collection.get(
                ids=matching_ids, include=["metadatas", "documents"]
            )

            # 格式化结果 (因为后续代码期望一个字典列表)
            formatted_results = []
            for i in range(len(results["ids"])):
                formatted_results.append(
                    {
                        "id": results["ids"][i],
                        "metadata": results["metadatas"][i],
                        "document": results["documents"][i],
                    }
                )

            self.db_view.current_list_items = formatted_results
            self.db_view.current_page = 0
            self.db_view.total_pages = (
                len(formatted_results) + self.db_view.items_per_page - 1
            ) // self.db_view.items_per_page
            self.db_view.search_mode = True
            self.db_view.search_keyword = keyword

            await self.db_view.update_view()
            await interaction.followup.send(
                f"✅ 找到 {len(formatted_results)} 条元数据包含 `{keyword}` 的帖子。",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"搜索向量数据库时发生错误: {e}", exc_info=True)
            await interaction.followup.send(f"搜索时发生错误: {e}", ephemeral=True)


# --- 数据库浏览器视图 ---
class DBView(discord.ui.View):
    """数据库浏览器的交互式视图"""

    def __init__(self, author_id: int):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.world_book_db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")
        self.chat_db_path = CHAT_DB_PATH
        self.message: Optional[discord.Message] = None

        # --- 状态管理 ---
        self.view_mode: str = "list"
        self.current_table: Optional[str] = None
        self.current_page: int = 0
        self.items_per_page: int = 10
        self.total_pages: int = 0
        self.current_item_id: Optional[str] = None
        self.current_list_items: List[sqlite3.Row] = []
        self.search_mode: bool = False
        self.search_keyword: Optional[str] = None

        # 初始化时就构建好初始组件
        self._initialize_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """确保只有命令发起者才能与视图交互"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "你不能操作这个视图。", ephemeral=True
            )
            return False
        return True

    def _get_db_connection(self):
        """根据当前选择的表，智能地连接到正确的数据库。"""
        # 'work_events' 和金币管理相关的功能使用 chat.db
        if self.current_table in ["work_events"]:
            db_path_to_use = self.chat_db_path
        # 其他（如社区成员、通用知识）使用 world_book.sqlite3
        else:
            db_path_to_use = self.world_book_db_path

        try:
            conn = sqlite3.connect(db_path_to_use)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到数据库 {db_path_to_use} 失败: {e}", exc_info=True)
            return None

    def _get_primary_key_column(self) -> str:
        """根据当前表返回主键列的名称。"""
        if self.current_table == "work_events":
            return "event_id"
        return "id"

    # --- UI 构建 ---

    def _initialize_components(self):
        """根据当前视图模式，动态构建UI组件"""
        self.clear_items()

        self.add_item(self._create_table_select())

        if self.view_mode == "list" and self.current_table:
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

            # --- 搜索功能按钮 ---
            button_row = 1
            # 社区成员：ID搜索 + 关键词搜索
            if self.current_table == "community_members":
                self.search_user_button = discord.ui.Button(
                    label="搜索用户",
                    emoji="🔍",
                    style=discord.ButtonStyle.success,
                    row=button_row,
                )
                self.search_user_button.callback = self.search_user
                self.add_item(self.search_user_button)

                if not self.search_mode:
                    self.search_member_button = discord.ui.Button(
                        label="关键词搜索",
                        emoji="🔍",
                        style=discord.ButtonStyle.primary,
                        row=button_row,
                    )
                    self.search_member_button.callback = self.search_community_member
                    self.add_item(self.search_member_button)

            # 通用知识：关键词搜索
            elif self.current_table == "general_knowledge" and not self.search_mode:
                self.search_knowledge_button = discord.ui.Button(
                    label="关键词搜索",
                    emoji="🔍",
                    style=discord.ButtonStyle.primary,
                    row=button_row,
                )
                self.search_knowledge_button.callback = self.search_knowledge
                self.add_item(self.search_knowledge_button)

            # 工作事件：关键词搜索
            elif self.current_table == "work_events" and not self.search_mode:
                self.search_work_event_button = discord.ui.Button(
                    label="关键词搜索",
                    emoji="🔍",
                    style=discord.ButtonStyle.primary,
                    row=button_row,
                )
                self.search_work_event_button.callback = self.search_work_event
                self.add_item(self.search_work_event_button)

            # 向量库：关键词搜索及管理功能
            elif self.current_table == "vector_db_metadata":
                if not self.search_mode:
                    self.search_vector_db_button = discord.ui.Button(
                        label="关键词搜索",
                        emoji="🔍",
                        style=discord.ButtonStyle.primary,
                        row=button_row,
                    )
                    self.search_vector_db_button.callback = self.search_vector_db
                    self.add_item(self.search_vector_db_button)

                # 新增：查询和索引缺失帖子的按钮
                self.query_missing_button = discord.ui.Button(
                    label="查询缺失帖子",
                    emoji="🔎",
                    style=discord.ButtonStyle.success,
                    row=button_row + 1,
                )
                self.query_missing_button.callback = self.query_missing_threads
                self.add_item(self.query_missing_button)

                self.index_missing_button = discord.ui.Button(
                    label="索引缺失帖子",
                    emoji="➕",
                    style=discord.ButtonStyle.danger,
                    row=button_row + 1,
                )
                self.index_missing_button.callback = self.index_missing_threads
                self.add_item(self.index_missing_button)

            # 通用：退出搜索模式的按钮
            if self.search_mode:
                self.exit_search_button = discord.ui.Button(
                    label="退出搜索",
                    emoji="❌",
                    style=discord.ButtonStyle.secondary,
                    row=button_row,
                )
                self.exit_search_button.callback = self.exit_search
                self.add_item(self.exit_search_button)

            if self.current_list_items:
                self.add_item(self._create_item_select())

        elif self.view_mode == "detail":
            self.back_button = discord.ui.Button(
                label="返回列表", emoji="⬅️", style=discord.ButtonStyle.secondary
            )
            self.back_button.callback = self.go_to_list_view
            self.add_item(self.back_button)

            # 向量数据库条目不可编辑或删除
            if self.current_table != "vector_db_metadata":
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

            # --- 新增：仅在查看社区成员时显示“查看记忆”按钮 ---
            if self.current_table == "community_members":
                self.view_memory_button = discord.ui.Button(
                    label="查看/编辑记忆", emoji="🧠", style=discord.ButtonStyle.success
                )
                self.view_memory_button.callback = self.view_memory
                self.add_item(self.view_memory_button)

    def _create_table_select(self) -> discord.ui.Select:
        """创建表格选择下拉菜单"""
        options = [
            discord.SelectOption(
                label="社区成员档案", value="community_members", emoji="👥"
            ),
            discord.SelectOption(
                label="通用知识", value="general_knowledge", emoji="📚"
            ),
            discord.SelectOption(
                label="类脑币管理", value="coin_management", emoji="🪙"
            ),
            discord.SelectOption(label="工作管理", value="work_events", emoji="💼"),
            discord.SelectOption(
                label="向量库元数据", value="vector_db_metadata", emoji="🧠"
            ),
        ]
        for option in options:
            if option.value == self.current_table:
                option.default = True

        select = discord.ui.Select(
            placeholder="请选择要查看的数据表...", options=options
        )
        select.callback = self.on_table_select
        return select

    def _create_item_select(self) -> discord.ui.Select:
        """根据当前列表页的条目创建选择菜单"""
        options = []
        if self.current_table == "vector_db_metadata":
            for item in self.current_list_items:
                title = self._get_entry_title(item)
                item_id = item["id"]
                label = f"#{item_id}"
                # 只有在标题有效时才添加
                if title and title != item_id:
                    label += f" - {title}"
                if len(label) > 100:
                    label = label[:97] + "..."
                options.append(discord.SelectOption(label=label, value=str(item_id)))
        else:
            pk = self._get_primary_key_column()
            for item in self.current_list_items:
                title = self._get_entry_title(item)
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

    async def on_table_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_value = interaction.data["values"][0]

        if selected_value == "coin_management":
            coin_view = CoinManagementView(interaction, self.message)
            await coin_view.update_view()
        else:
            self.current_table = selected_value
            self.current_page = 0
            self.view_mode = "list"
            self.search_mode = False
            self.search_keyword = None
            await self.update_view()

    async def on_item_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_item_id = interaction.data["values"][0]
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
        """显示一个模态窗口让用户输入页码"""
        if self.total_pages > 1:
            modal = JumpToPageModal(self)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(
                "只有一页，无需跳转。", ephemeral=True
            )

    async def search_user(self, interaction: discord.Interaction):
        """显示一个模态窗口让用户输入 Discord ID 进行搜索"""
        modal = SearchUserModal(self)
        await interaction.response.send_modal(modal)

    async def search_knowledge(self, interaction: discord.Interaction):
        """显示一个模态窗口让用户输入关键词搜索社区知识"""
        modal = SearchKnowledgeModal(self)
        await interaction.response.send_modal(modal)

    async def search_work_event(self, interaction: discord.Interaction):
        """显示一个模态窗口让用户输入关键词搜索工作事件"""
        modal = SearchWorkEventModal(self)
        await interaction.response.send_modal(modal)

    async def search_community_member(self, interaction: discord.Interaction):
        """显示一个模态窗口让用户输入关键词搜索社区成员"""
        modal = SearchCommunityMemberModal(self)
        await interaction.response.send_modal(modal)

    async def search_vector_db(self, interaction: discord.Interaction):
        """显示一个模态窗口让用户输入关键词搜索向量数据库"""
        modal = SearchVectorDBModal(self)
        await interaction.response.send_modal(modal)

    async def exit_search(self, interaction: discord.Interaction):
        """退出搜索模式，恢复正常浏览"""
        await interaction.response.defer()
        self.search_mode = False
        self.search_keyword = None
        self.current_page = 0
        await self.update_view()

    async def query_missing_threads(self, interaction: discord.Interaction):
        """查询并报告在向量数据库中缺失的帖子"""
        await interaction.response.send_message(
            "⏳ 正在开始查询，这可能需要几分钟时间，请稍候...", ephemeral=True
        )

        try:
            bot = interaction.client
            all_forum_thread_ids = set()
            total_channels_queried = 0

            for channel_id in chat_config.FORUM_SEARCH_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if isinstance(channel, discord.ForumChannel):
                    total_channels_queried += 1
                    try:
                        # 获取活跃帖子
                        for thread in channel.threads:
                            all_forum_thread_ids.add(thread.id)
                        # 获取归档帖子
                        async for thread in channel.archived_threads(limit=None):
                            all_forum_thread_ids.add(thread.id)
                    except discord.errors.Forbidden:
                        log.warning(
                            f"机器人缺少访问频道 {channel.name} ({channel.id}) 中帖子的权限。已跳过此频道。"
                        )
                        continue

            log.info(f"从 Discord API 获取到 {len(all_forum_thread_ids)} 个总帖子 ID。")

            # 从向量数据库获取所有已索引的帖子ID
            indexed_thread_ids = set(
                forum_vector_db_service.get_all_indexed_thread_ids()
            )
            log.info(f"从向量数据库获取到 {len(indexed_thread_ids)} 个已索引帖子 ID。")

            missing_thread_ids = all_forum_thread_ids - indexed_thread_ids
            missing_count = len(missing_thread_ids)

            if missing_count == 0:
                await interaction.followup.send(
                    f"✅ **查询完成**\n\n在查询的 **{total_channels_queried}** 个频道中，所有帖子均已成功索引，没有发现缺失。",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"⚠️ **查询完成**\n\n在查询的 **{total_channels_queried}** 个频道中，共发现 **{missing_count}** 个帖子尚未被索引。\n"
                    "你可以点击“索引缺失帖子”按钮来处理它们。",
                    ephemeral=True,
                )

        except Exception as e:
            log.error(f"查询缺失帖子时出错: {e}", exc_info=True)
            await interaction.followup.send(f"查询时发生错误: {e}", ephemeral=True)

    async def index_missing_threads(self, interaction: discord.Interaction):
        """在一个后台任务中索引所有缺失的帖子"""
        await interaction.response.send_message(
            "⏳ **任务已启动**\n\n正在后台开始索引所有缺失的帖子。这个过程可能需要很长时间。\n"
            "完成后会在此频道发送一条消息通知你。",
            ephemeral=True,
        )

        # 创建一个后台任务来执行耗时的索引操作
        asyncio.create_task(self._background_index_task(interaction))

    async def _background_index_task(self, interaction: discord.Interaction):
        """实际执行索引的后台函数"""
        try:
            bot = interaction.client
            all_forum_thread_ids = set()
            for channel_id in chat_config.FORUM_SEARCH_CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if isinstance(channel, discord.ForumChannel):
                    try:
                        for thread in channel.threads:
                            all_forum_thread_ids.add(thread.id)
                        async for thread in channel.archived_threads(limit=None):
                            all_forum_thread_ids.add(thread.id)
                    except discord.errors.Forbidden:
                        log.warning(
                            f"后台索引任务：机器人缺少访问频道 {channel.name} ({channel.id}) 中帖子的权限。已跳过此频道。"
                        )
                        continue

            indexed_thread_ids = set(
                forum_vector_db_service.get_all_indexed_thread_ids()
            )
            missing_thread_ids = list(all_forum_thread_ids - indexed_thread_ids)
            missing_count = len(missing_thread_ids)

            if missing_count == 0:
                await interaction.followup.send(
                    "✅ **索引任务完成**\n\n没有发现需要索引的帖子。", ephemeral=True
                )
                return

            log.info(f"开始后台索引 {missing_count} 个缺失的帖子...")
            processed_count = 0
            for thread_id in missing_thread_ids:
                try:
                    thread = await bot.fetch_channel(thread_id)
                    if isinstance(thread, discord.Thread):
                        await forum_search_service.process_thread(thread)
                        processed_count += 1
                        # 每处理10个帖子就短暂休息一下，避免API过载
                        if processed_count % 10 == 0:
                            log.info(
                                f"已处理 {processed_count}/{missing_count} 个帖子，暂停2秒..."
                            )
                            await asyncio.sleep(2)
                except discord.NotFound:
                    log.warning(f"无法找到帖子 ID {thread_id}，可能已被删除。")
                except Exception as e:
                    log.error(f"处理帖子 ID {thread_id} 时出错: {e}", exc_info=True)

            log.info("后台索引任务完成。")
            await interaction.followup.send(
                f"✅ **索引任务完成**\n\n成功处理了 **{processed_count} / {missing_count}** 个缺失的帖子。",
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"后台索引任务发生严重错误: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **索引任务失败**\n\n后台任务发生严重错误: {e}", ephemeral=True
            )

    async def view_memory(self, interaction: discord.Interaction):
        """打开模态框以查看和编辑社区成员的个人记忆摘要"""
        if not self.current_item_id or self.current_table != "community_members":
            # 虽然 interaction_check 会处理，但这里提前返回更清晰
            return

        # response.defer() 将在 modal 中处理，这里不需要

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item or "discord_number_id" not in current_item.keys():
            await interaction.response.send_message(
                "无法获取该成员的 Discord ID。", ephemeral=True
            )
            return

        discord_id = current_item["discord_number_id"]
        if not discord_id:
            await interaction.response.send_message(
                "该成员未记录 Discord ID，无法查询记忆。", ephemeral=True
            )
            return

        try:
            user_id = int(discord_id)
            # 先获取当前的记忆摘要
            current_summary = await personal_memory_service.get_memory_summary(user_id)
            member_name = (
                self._get_entry_title(current_item) or f"ID: {discord_id}"
            ).replace("社区成员档案 - ", "")

            # 创建并发送模态框
            modal = EditMemoryModal(self, user_id, member_name, current_summary)
            await interaction.response.send_modal(modal)

        except ValueError:
            await interaction.response.send_message(
                f"无效的 Discord ID 格式: `{discord_id}`", ephemeral=True
            )
        except Exception as e:
            log.error(f"打开记忆编辑模态框时出错: {e}", exc_info=True)
            await interaction.response.send_message(
                f"处理请求时发生错误: {e}", ephemeral=True
            )

    # --- 数据操作 ---

    async def find_user_and_jump(self, interaction: discord.Interaction, user_id: str):
        """根据 Discord ID 查找用户并跳转到其所在页面"""
        if self.current_table != "community_members":
            return

        conn = self._get_db_connection()
        if not conn:
            await interaction.followup.send("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = conn.cursor()
            # 1. 获取所有用户的 ID 和 discord_number_id，按主键排序
            cursor.execute(
                "SELECT id, discord_number_id FROM community_members ORDER BY id DESC"
            )
            all_users = cursor.fetchall()

            # 2. 在 Python 中查找目标用户
            target_index = -1
            target_user_db_id = None
            for i, user in enumerate(all_users):
                if str(user["discord_number_id"]) == user_id:
                    target_index = i
                    target_user_db_id = user["id"]
                    break

            # 3. 如果找到，计算页码并更新视图
            if target_index != -1:
                page = target_index // self.items_per_page
                position_on_page = (target_index % self.items_per_page) + 1
                self.current_page = page

                await self.update_view()

                await interaction.followup.send(
                    f"✅ 用户 `{user_id}` 已找到。\n"
                    f"跳转到第 **{page + 1}** 页，其档案 `#{target_user_db_id}` 是该页的第 **{position_on_page}** 个。",
                    ephemeral=True,
                )
            else:
                # --- 新增逻辑：如果找不到社区成员档案，则检查是否存在个人记忆 ---
                try:
                    user_id_int = int(user_id)
                    memory_summary = await personal_memory_service.get_memory_summary(
                        user_id_int
                    )
                    # 检查记忆是否存在（不是None也不是空字符串）
                    if memory_summary is not None:
                        log.info(
                            f"未找到社区成员档案，但找到了用户 {user_id} 的个人记忆，直接打开编辑窗口。"
                        )
                        # 获取用户对象以显示名称，如果获取不到就用ID代替
                        try:
                            member = await interaction.guild.fetch_member(user_id_int)
                            member_name = member.display_name
                        except discord.NotFound:
                            member_name = f"用户 {user_id}"

                        modal = EditMemoryModal(
                            self, user_id_int, member_name, memory_summary
                        )
                        # 因为之前的 on_submit 已经 defer()，这里不能再用 response.send_modal
                        # 需要通过 followup 发送一个提示，然后让用户手动操作或找到更好的 modal 调用方式
                        # 在当前 discord.py 版本中，interaction 在 defer 后只能 followup
                        # 直接发送 modal 是 interaction response 的一部分，不能在 followup 中使用
                        # 因此，我们先发送一个提示消息
                        await interaction.followup.send(
                            "ℹ️ 未找到该用户的社区档案，但找到了其个人记忆。",
                            ephemeral=True,
                        )
                        modal = EditMemoryModal(
                            self,
                            user_id_int,
                            f"用户 {user_id}",  # 暂时无法获取名字
                            memory_summary,
                        )
                        # 我们不能在这里发送 modal，因为 SearchUserModal 已经 defer 了。
                        # 我们必须在 SearchUserModal.on_submit 中处理。
                        # 所以，我将在这里添加逻辑，然后在下一个步骤中重构它。
                        await interaction.followup.send(
                            "❌ 未在社区成员档案中找到该用户，但检测到其拥有个人记忆。\n"
                            "请在详情页点击“查看/编辑记忆”按钮进行修改。",
                            ephemeral=True,
                        )

                    else:
                        await interaction.followup.send(
                            f"❌ 未找到 Discord ID 为 `{user_id}` 的用户。",
                            ephemeral=True,
                        )
                except ValueError:
                    await interaction.followup.send(
                        f"❌ 无效的 Discord ID `{user_id}`。", ephemeral=True
                    )
                except Exception as e:
                    log.error(f"搜索用户时发生意外错误: {e}", exc_info=True)
                    await interaction.followup.send(
                        f"搜索时发生未知错误: {e}", ephemeral=True
                    )

        except sqlite3.Error as e:
            log.error(f"搜索用户时发生数据库错误: {e}", exc_info=True)
            await interaction.followup.send(f"搜索时发生错误: {e}", ephemeral=True)
        finally:
            if conn:
                conn.close()

    def _get_item_by_id(self, item_id: str) -> Optional[sqlite3.Row]:
        conn = self._get_db_connection()
        if not conn or not self.current_table:
            return None
        try:
            pk = self._get_primary_key_column()
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {self.current_table} WHERE {pk} = ?", (item_id,)
            )
            return cursor.fetchone()
        finally:
            if conn:
                conn.close()

    def _get_entry_title(self, entry: sqlite3.Row) -> str:
        """
        根据表名和数据结构，为数据库条目获取最合适的标题。
        """
        try:
            if self.current_table == "vector_db_metadata":
                # 对于向量数据库，我们从 metadata 中获取标题和作者
                metadata = entry.get("metadata", {})
                title = metadata.get("thread_name", "无标题")
                author_name = metadata.get("author_name", "未知作者")
                return f"标题: {title} - 作者: {author_name}"

            # 1. 社区成员档案：直接使用 title 字段
            if self.current_table == "community_members":
                return entry["title"]

            # 2. 通用知识：直接使用 title 字段
            elif self.current_table == "general_knowledge":
                return entry["title"]

            # 3. 工作事件：使用 name 字段
            elif self.current_table == "work_events":
                return entry["name"]

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pk = self._get_primary_key_column()
            item_id = entry.get(pk, entry.get("id", "N/A"))
            log.warning(f"解析条目 #{item_id} 标题时出错: {e}")
            return f"ID: #{item_id} (解析错误)"

        # 3. 回退机制：以防未来有其他表
        pk = self._get_primary_key_column()
        return f"ID: #{entry.get(pk, entry.get('id', 'N/A'))}"

    def _truncate_field_value(self, value: any) -> str:
        """将值截断以符合 Discord embed 字段值的长度限制。"""
        value_str = str(value)
        if len(value_str) > 1024:
            # 检查是否是代码块
            if value_str.startswith("```") and value_str.endswith("```"):
                # 为 "...\n```" 留出空间
                return value_str[:1017] + "...\n```"
            else:
                return value_str[:1021] + "..."
        return value_str

    async def edit_item(self, interaction: discord.Interaction):
        if not self.current_item_id:
            return await interaction.response.send_message(
                "没有可编辑的条目。", ephemeral=True
            )

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            return await interaction.response.send_message(
                "找不到指定的条目。", ephemeral=True
            )

        # 根据表名选择不同的模态框
        if self.current_table == "community_members":
            modal = EditCommunityMemberModal(self, self.current_item_id, current_item)
        elif self.current_table == "work_events":
            modal = EditWorkEventModal(self, self.current_item_id, current_item)
        else:
            modal = EditModal(
                self, self.current_table, self.current_item_id, current_item
            )

        await interaction.response.send_modal(modal)

    async def delete_item(self, interaction: discord.Interaction):
        if not self.current_item_id:
            return await interaction.response.send_message(
                "没有可删除的条目。", ephemeral=True
            )
        item_id = self.current_item_id

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(inner_interaction: discord.Interaction):
            conn = self._get_db_connection()
            if not conn:
                return await inner_interaction.response.edit_message(
                    content="数据库连接失败。", view=None
                )
            try:
                cursor = conn.cursor()
                pk = self._get_primary_key_column()
                cursor.execute(
                    f"DELETE FROM {self.current_table} WHERE {pk} = ?", (item_id,)
                )
                conn.commit()
                log.info(
                    f"管理员 {interaction.user.display_name} 删除了表 '{self.current_table}' 的记录 ID {item_id}。"
                )
                await inner_interaction.response.edit_message(
                    content=f"🗑️ 记录 `#{item_id}` 已被成功删除。", view=None
                )

                # --- RAG 删除 ---
                log.info(f"开始从向量数据库中删除条目 {item_id}...")
                await incremental_rag_service.delete_entry(item_id)
                log.info(f"条目 {item_id} 的向量已成功删除。")

                self.view_mode = "list"
                conn_check = self._get_db_connection()
                if conn_check:
                    try:
                        cursor_check = conn_check.cursor()
                        cursor_check.execute(
                            f"SELECT COUNT(*) FROM {self.current_table}"
                        )
                        total_rows = cursor_check.fetchone()[0]
                        new_total_pages = (
                            total_rows + self.items_per_page - 1
                        ) // self.items_per_page
                        if (
                            self.current_page >= new_total_pages
                            and self.current_page > 0
                        ):
                            self.current_page -= 1
                    finally:
                        conn_check.close()
                await self.update_view()
            except sqlite3.Error as e:
                await inner_interaction.response.edit_message(
                    content=f"删除失败: {e}", view=None
                )
            finally:
                if conn:
                    conn.close()

        async def cancel_callback(inner_interaction: discord.Interaction):
            await inner_interaction.response.edit_message(
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

    # --- 视图更新 ---

    async def update_view(self):
        """根据当前状态更新视图消息"""
        if not self.message:
            log.warning("DBView 尝试更新视图，但没有关联的 message 对象。")
            return

        if self.current_table == "vector_db_metadata":
            if self.view_mode == "list":
                embed = await self._build_vector_db_list_embed()
            else:
                embed = await self._build_vector_db_detail_embed()
        elif self.view_mode == "list":
            embed = await self._build_list_embed()
        else:
            embed = await self._build_detail_embed()

        self._initialize_components()

        try:
            await self.message.edit(embed=embed, view=self)
        except discord.errors.NotFound:
            log.warning("尝试编辑 DBView 消息失败，消息可能已被删除。")
        except discord.errors.HTTPException as e:
            log.error(f"编辑 DBView 消息时发生 HTTP 错误: {e}", exc_info=True)

    async def _build_list_embed(self) -> discord.Embed:
        conn = self._get_db_connection()
        if not conn or not self.current_table:
            return discord.Embed(
                title="🗂️ 数据库浏览器",
                description="请从下方的菜单中选择一个数据表进行查看。",
                color=discord.Color.blurple(),
            )

        try:
            cursor = conn.cursor()

            # 如果是搜索模式，使用已加载的搜索结果
            if self.search_mode:
                start_idx = self.current_page * self.items_per_page
                end_idx = start_idx + self.items_per_page
                page_items = self.current_list_items[start_idx:end_idx]

                table_name_map = {
                    "community_members": "社区成员档案",
                    "general_knowledge": "通用知识",
                    "work_events": "工作事件",
                }
                table_display_name = table_name_map.get(
                    self.current_table, self.current_table
                )

                embed = discord.Embed(
                    title=f"搜索: {table_display_name} (关键词: '{self.search_keyword}')",
                    color=discord.Color.gold(),
                )

                if not page_items:
                    embed.description = "当前页没有搜索结果。"
                else:
                    pk = self._get_primary_key_column()
                    list_text = "\n".join(
                        [
                            f"**`#{item[pk]}`** - {self._get_entry_title(item)}"
                            for item in page_items
                        ]
                    )
                    embed.description = list_text

                embed.set_footer(
                    text=f"第 {self.current_page + 1} / {self.total_pages or 1} 页 (共 {len(self.current_list_items)} 条结果)"
                )
                return embed

            # 正常浏览模式
            cursor.execute(f"SELECT COUNT(*) FROM {self.current_table}")
            total_rows = cursor.fetchone()[0]
            self.total_pages = (
                total_rows + self.items_per_page - 1
            ) // self.items_per_page
            offset = self.current_page * self.items_per_page
            # 根据不同的表使用不同的排序方式，确保最新创建的条目在第一页
            if self.current_table == "general_knowledge":
                # 通用知识按创建时间降序排序（最新的在前）
                cursor.execute(
                    f"SELECT * FROM {self.current_table} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                    (self.items_per_page, offset),
                )
            elif self.current_table == "community_members":
                # 社区成员档案按ID降序排序（最新的在前）
                cursor.execute(
                    f"SELECT * FROM {self.current_table} ORDER BY id DESC LIMIT ? OFFSET ?",
                    (self.items_per_page, offset),
                )
            else:
                # 其他表默认按其主键降序排序
                pk = self._get_primary_key_column()
                cursor.execute(
                    f"SELECT * FROM {self.current_table} ORDER BY {pk} DESC LIMIT ? OFFSET ?",
                    (self.items_per_page, offset),
                )
            self.current_list_items = cursor.fetchall()

            table_name_map = {
                "community_members": "社区成员档案",
                "general_knowledge": "通用知识",
                "work_events": "工作事件",
            }
            table_display_name = table_name_map.get(
                self.current_table, self.current_table
            )

            embed = discord.Embed(
                title=f"浏览：{table_display_name}", color=discord.Color.green()
            )

            if not self.current_list_items:
                embed.description = "这个表中目前没有数据。"
            else:
                pk = self._get_primary_key_column()
                list_text = "\n".join(
                    [
                        f"**`#{item[pk]}`** - {self._get_entry_title(item)}"
                        for item in self.current_list_items
                    ]
                )
                embed.description = list_text

            embed.set_footer(
                text=f"第 {self.current_page + 1} / {self.total_pages or 1} 页"
            )
            return embed
        except sqlite3.Error as e:
            log.error(f"更新数据库列表视图时出错: {e}", exc_info=True)
            return discord.Embed(
                title="数据库错误",
                description=f"加载表 `{self.current_table}` 时发生错误: {e}",
                color=discord.Color.red(),
            )
        finally:
            if conn:
                conn.close()

    async def _build_detail_embed(self) -> discord.Embed:
        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            self.view_mode = "list"
            return await self._build_list_embed()

        try:
            title = self._get_entry_title(current_item)
            embed = discord.Embed(
                title=f"查看详情: {title}",
                description=f"表: `{self.current_table}` | ID: `#{self.current_item_id}`",
                color=discord.Color.blue(),
            )
            for col in current_item.keys():
                value = current_item[col]
                # 美化 JSON 显示
                if isinstance(value, str) and (
                    value.startswith("{") or value.startswith("[")
                ):
                    try:
                        parsed_json = json.loads(value)
                        value = f"```json\n{json.dumps(parsed_json, indent=2, ensure_ascii=False)}\n```"
                    except json.JSONDecodeError:
                        value = f"```\n{value}\n```"  # 如果不是标准JSON，也用代码块包裹

                # 处理空值
                if value is None or str(value).strip() == "":
                    value = "_(空)_"

                embed.add_field(
                    name=col.replace("_", " ").title(),
                    value=self._truncate_field_value(value),
                    inline=False,
                )
            return embed
        except Exception as e:
            log.error(f"获取条目详情时出错: {e}", exc_info=True)
            return discord.Embed(
                title="数据库错误",
                description=f"加载 ID 为 {self.current_item_id} 的条目时发生错误: {e}",
                color=discord.Color.red(),
            )

    async def _build_vector_db_list_embed(self) -> discord.Embed:
        """构建向量数据库的列表视图"""
        table_display_name = "向量库元数据 (帖子搜索)"
        try:
            if not forum_vector_db_service or not forum_vector_db_service.client:
                raise ConnectionError("未能连接到向量数据库服务。")

            collection = forum_vector_db_service.client.get_collection(
                name=forum_vector_db_service.collection_name
            )

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
                total_items = collection.count()
                offset = self.current_page * self.items_per_page
                results = collection.get(
                    limit=self.items_per_page,
                    offset=offset,
                    include=["metadatas", "documents"],
                )
                # 格式化为字典列表
                page_items = []
                for i in range(len(results["ids"])):
                    page_items.append(
                        {
                            "id": results["ids"][i],
                            "metadata": results["metadatas"][i],
                            "document": results["documents"][i],
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
                        f"**`#{item['id']}`** - {self._get_entry_title(item)}"
                        for item in self.current_list_items
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

    async def _build_vector_db_detail_embed(self) -> discord.Embed:
        """构建向量数据库的详情视图"""
        if not self.current_item_id:
            self.view_mode = "list"
            return await self._build_vector_db_list_embed()

        try:
            if not forum_vector_db_service or not forum_vector_db_service.client:
                raise ConnectionError("未能连接到向量数据库服务。")

            collection = forum_vector_db_service.client.get_collection(
                name=forum_vector_db_service.collection_name
            )
            results = collection.get(
                ids=[self.current_item_id], include=["metadatas", "documents"]
            )

            if not results or not results["ids"]:
                await self.go_to_list_view()
                return discord.Embed(
                    title="错误",
                    description=f"找不到 ID 为 `{self.current_item_id}` 的条目。",
                    color=discord.Color.red(),
                )

            item = {
                "id": results["ids"][0],
                "metadata": results["metadatas"][0],
                "document": results["documents"][0],
            }

            title = self._get_entry_title(item)
            embed = discord.Embed(
                title=f"查看向量详情: {title}",
                description=f"表: `向量数据库` | ID: `#{item['id']}`",
                color=discord.Color.purple(),
            )

            # 显示所有元数据
            if item["metadata"]:
                for key, value in item["metadata"].items():
                    embed.add_field(
                        name=key.replace("_", " ").title(),
                        value=self._truncate_field_value(value),
                        inline=True,
                    )

            # 显示文档内容
            if item["document"]:
                # 健壮地解析 document 文本，分离标题和内容，兼容新旧格式
                document_content = item["document"].strip()
                doc_title = "_(无标题)_"
                doc_body = "_(无内容)_"

                # 以 "\n内容: " 为分隔符，将文档分为头部和内容两部分
                content_parts = document_content.split("\n内容: ", 1)
                header_block = content_parts[0]
                if len(content_parts) == 2:
                    doc_body = content_parts[1].strip()

                # 从头部块中解析标题
                title_tag = "标题: "
                if header_block.strip().startswith(title_tag):
                    # 提取 "标题: " 所在行的内容作为标题
                    title_line = header_block.strip().split("\n")[0]
                    doc_title = title_line[len(title_tag) :].strip()
                else:
                    # 如果没有 "标题: " 标签，将头部块的第一行作为备用标题
                    doc_title = header_block.strip().split("\n")[0]

                embed.add_field(
                    name="向量化文本 (RAG Data)",
                    value=self._truncate_field_value(
                        f"**标题:** {doc_title}\n**内容:** {doc_body}"
                    ),
                    inline=False,
                )

            return embed

        except Exception as e:
            log.error(f"获取向量数据库条目详情时出错: {e}", exc_info=True)
            return discord.Embed(
                title="错误",
                description=f"加载 ID 为 {self.current_item_id} 的条目时发生错误: {e}",
                color=discord.Color.red(),
            )
