# -*- coding: utf-8 -*-

import discord
import logging
import sqlite3
import json

from src.chat.features.world_book.services.incremental_rag_service import (
    incremental_rag_service,
)
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)

from ..typing import AnyDBView

log = logging.getLogger(__name__)


# --- 新增：编辑个人记忆的模态窗口 ---
class EditMemoryModal(discord.ui.Modal):
    def __init__(
        self, db_view: AnyDBView, user_id: int, member_name: str, current_summary: str
    ):
        # --- 标题截断 ---
        title_prefix = "编辑 "
        title_suffix = " 的记忆"
        # 计算 `member_name` 的最大允许长度
        max_name_len = 45 - len(title_prefix) - len(title_suffix)

        truncated_name = member_name
        # 如果 `member_name` 太长，则截断并添加省略号
        if len(member_name) > max_name_len:
            # 减去3是为了给 "..." 留出空间
            truncated_name = member_name[: max_name_len - 3] + "..."

        super().__init__(title=f"{title_prefix}{truncated_name}{title_suffix}")
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


# --- 编辑社区成员的模态窗口 ---
class EditCommunityMemberModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView, item_id: str, current_data: dict):
        modal_title = f"编辑社区成员档案 #{item_id}"
        if len(modal_title) > 45:
            modal_title = modal_title[:42] + "..."
        super().__init__(title=modal_title)
        self.db_view = db_view
        self.item_id = item_id
        self.current_data = dict(current_data) if current_data else {}

        # --- 从 full_text 或 source_metadata 中解析数据 ---
        content_data = {}
        full_text = self.current_data.get("full_text", "")
        source_metadata = self.current_data.get("source_metadata", {})

        # 首先尝试从 full_text 中解析 JSON 数据
        if full_text:
            # 清理 full_text：去除开头的换行符和空白
            cleaned_full_text = full_text.strip()
            # 尝试解析为 JSON
            try:
                # 查找 JSON 部分（full_text 可能包含换行符和 JSON）
                if cleaned_full_text.startswith("{"):
                    content_data = json.loads(cleaned_full_text)
                elif '{"name":' in cleaned_full_text:
                    # 提取 JSON 部分
                    json_start = cleaned_full_text.find("{")
                    json_end = cleaned_full_text.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = cleaned_full_text[json_start:json_end]
                        content_data = json.loads(json_str)
            except (json.JSONDecodeError, TypeError) as e:
                log.warning(
                    f"无法解析 community.member_profiles #{self.item_id} 的 full_text: {e}"
                )

        # 如果 full_text 中没有解析出数据，尝试从 source_metadata 中解析
        if not content_data and source_metadata:
            try:
                if isinstance(source_metadata, str):
                    # 尝试解析为 JSON
                    try:
                        metadata = json.loads(source_metadata)
                    except json.JSONDecodeError:
                        # 如果不是标准 JSON，尝试使用 ast.literal_eval 解析 Python 字典
                        import ast

                        metadata = ast.literal_eval(source_metadata)
                else:
                    metadata = source_metadata

                # 从 source_metadata 的 content_json 字段中提取数据
                if "content_json" in metadata:
                    content_json_str = metadata["content_json"]
                    if isinstance(content_json_str, str):
                        content_data = json.loads(content_json_str)
                    else:
                        content_data = content_json_str
                else:
                    # 如果没有 content_json，使用 metadata 本身
                    content_data = metadata
            except (json.JSONDecodeError, TypeError, ValueError, SyntaxError) as e:
                log.warning(
                    f"无法解析 community.member_profiles #{self.item_id} 的 source_metadata: {e}"
                )

        # 成员名称 - 从 title 或 source_metadata 中获取
        name = ""
        if "name" in content_data:
            name = content_data.get("name", "")
        elif "title" in self.current_data:
            title = self.current_data.get("title", "")
            if title and "社区成员档案 - " in title:
                name = title.replace("社区成员档案 - ", "")

        self.name_input = discord.ui.TextInput(
            label="成员名称 (name)",
            default=name,
            max_length=100,
            required=True,
        )
        self.add_item(self.name_input)

        # Discord ID - 从 discord_id 字段获取
        discord_id = self.current_data.get("discord_id", "")
        self.discord_id_input = discord.ui.TextInput(
            label="Discord ID",
            default=str(discord_id),
            max_length=20,
            required=True,
        )
        self.add_item(self.discord_id_input)

        # 性格特点
        self.personality_input = discord.ui.TextInput(
            label="性格特点 (personality)",
            default=content_data.get("personality", ""),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.personality_input)

        # 背景信息
        self.background_input = discord.ui.TextInput(
            label="背景信息 (background)",
            default=content_data.get("background", ""),
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
        )
        self.add_item(self.background_input)

        # 喜好偏好
        self.preferences_input = discord.ui.TextInput(
            label="喜好偏好 (preferences)",
            default=content_data.get("preferences", ""),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.add_item(self.preferences_input)

    async def on_submit(self, interaction: discord.Interaction):
        conn = self.db_view._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            # 根据数据库类型选择正确的游标
            from src.chat.features.admin_panel.services import db_services

            cursor = db_services.get_cursor(conn)

            # 从模态窗口的子组件中获取更新后的值
            updated_name = self.name_input.value.strip()
            updated_discord_id = self.discord_id_input.value.strip()

            # 构建完整的文本内容
            full_text = f"""
名称: {updated_name}
Discord ID: {updated_discord_id}
性格特点: {self.personality_input.value.strip()}
背景信息: {self.background_input.value.strip()}
喜好偏好: {self.preferences_input.value.strip()}
            """.strip()

            # 构建 source_metadata
            source_metadata = {
                "name": updated_name,
                "discord_id": updated_discord_id,
                "personality": self.personality_input.value.strip(),
                "background": self.background_input.value.strip(),
                "preferences": self.preferences_input.value.strip(),
                "updated_by": str(interaction.user.id),
                "updated_at": "now()",
            }

            # 构建 SQL 更新语句（只支持 PostgreSQL/ParadeDB）
            sql = """
                UPDATE community.member_profiles
                SET title = %s, discord_id = %s, full_text = %s, source_metadata = %s, updated_at = NOW()
                WHERE id = %s
            """
            params = (
                updated_name,  # 存储纯名称，不加前缀
                updated_discord_id,
                full_text,
                json.dumps(source_metadata, ensure_ascii=False),
                self.item_id,
            )

            cursor.execute(sql, params)
            conn.commit()
            log.info(
                f"管理员 {interaction.user.display_name} 成功更新了表 'community.member_profiles' 中 ID 为 {self.item_id} 的记录。"
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

        except Exception as e:
            log.error(f"更新社区成员档案失败: {e}", exc_info=True)
            await interaction.response.send_message(f"更新失败: {e}", ephemeral=True)
        finally:
            if conn:
                conn.close()


# --- 编辑工作事件的模态窗口 (已更新为倍率模型) ---
class EditWorkEventModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView, item_id: str, current_data: sqlite3.Row):
        super().__init__(title=f"编辑工作事件 #{item_id}")
        self.db_view = db_view
        self.item_id = item_id
        self.current_data = dict(current_data)

        # 1. 事件名称
        self.name_input = discord.ui.TextInput(
            label="事件名称",
            default=self.current_data.get("name", ""),
            required=True,
        )
        self.add_item(self.name_input)

        # 2. 事件描述
        self.description_input = discord.ui.TextInput(
            label="事件描述",
            default=self.current_data.get("description", ""),
            style=discord.TextStyle.paragraph,
            required=True,
        )
        self.add_item(self.description_input)

        # 3. 基础奖励范围
        self.reward_range_input = discord.ui.TextInput(
            label="基础奖励范围 (最小,最大)",
            placeholder="例如: 200,500",
            default=f"{self.current_data.get('reward_range_min', '')},{self.current_data.get('reward_range_max', '')}",
            required=True,
        )
        self.add_item(self.reward_range_input)

        # 4. 好事
        self.good_event_input = discord.ui.TextInput(
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
        self.add_item(self.good_event_input)

        # 5. 坏事
        self.bad_event_input = discord.ui.TextInput(
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
        self.add_item(self.bad_event_input)

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
                    self.reward_range_input.value.strip().split(",")
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
            good_event_str = self.good_event_input.value.strip()
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
            bad_event_str = self.bad_event_input.value.strip()
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
                self.name_input.value.strip(),  # name
                self.description_input.value.strip(),  # description
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
        db_view: AnyDBView,
        table_name: str,
        item_id: str,
        current_data: sqlite3.Row,
    ):
        # 构造并截断标题以防止超长
        self.db_view = db_view  # 修正: 将传入的 db_view 实例赋值给 self
        raw_title = self.db_view._get_entry_title(dict(current_data))
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
            style = discord.TextStyle.short
            default_text = str(value) if value is not None else ""

            # 检查值是否为字典或可能是 JSON 字符串
            is_json_like = isinstance(value, dict) or (
                isinstance(value, str) and value.strip().startswith(("{", "["))
            )

            if is_json_like:
                try:
                    # 如果是字符串，先加载它；如果是字典，直接使用
                    json_data = json.loads(value) if isinstance(value, str) else value
                    # 转储为格式化的 JSON 字符串用于显示
                    default_text = json.dumps(json_data, indent=2, ensure_ascii=False)
                    style = discord.TextStyle.paragraph
                except (json.JSONDecodeError, TypeError):
                    # 如果解析或转储失败，则回退到简单的字符串转换
                    default_text = str(value) if value is not None else ""

            # 如果内容很长，即使不是 JSON，也使用段落样式
            if style == discord.TextStyle.short and len(default_text) > 100:
                style = discord.TextStyle.paragraph

            self.add_item(
                discord.ui.TextInput(
                    label=col,
                    default=default_text,
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
            from src.chat.features.admin_panel.services import db_services

            cursor = db_services.get_cursor(conn)

            update_fields = []
            update_values = []

            # 从模态窗口的子组件中获取更新后的值
            for component in self.children:
                if isinstance(component, discord.ui.TextInput):
                    # 使用 %s 作为占位符
                    update_fields.append(f'"{component.label}" = %s')
                    update_values.append(component.value)

            update_values.append(self.item_id)

            # 构建并执行 SQL 更新语句
            # 使用 %s 作为 WHERE 子句的占位符
            sql = (
                f"UPDATE {self.table_name} SET {', '.join(update_fields)} WHERE id = %s"
            )

            log.debug(f"Executing SQL: {sql}")
            log.debug(f"With params: {tuple(update_values)}")

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
            if self.table_name == "community.member_profiles":
                await incremental_rag_service.process_community_member(self.item_id)
            elif self.table_name == "general_knowledge.knowledge_documents":
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
