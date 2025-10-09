# -*- coding: utf-8 -*-

import discord
import logging
import sqlite3
import os
import json
from typing import List, Optional

from src import config
from src.chat.features.world_book.services.incremental_rag_service import incremental_rag_service

log = logging.getLogger(__name__)

# --- 编辑社区成员的模态窗口 ---
class EditCommunityMemberModal(discord.ui.Modal):
    def __init__(self, db_view: 'DBView', item_id: str, current_data: sqlite3.Row):
        modal_title = f"编辑社区成员档案 #{item_id}"
        if len(modal_title) > 45:
            modal_title = modal_title[:42] + "..."
        super().__init__(title=modal_title)
        self.db_view = db_view
        self.item_id = item_id
        self.current_data = dict(current_data) if current_data else {}

        # --- 从 content_json 中解析数据 ---
        content_data = {}
        if 'content_json' in self.current_data:
            try:
                content_data = json.loads(self.current_data['content_json'])
            except (json.JSONDecodeError, TypeError):
                log.warning(f"无法解析 community_members #{self.item_id} 的 content_json。")

        # 成员名称
        self.add_item(discord.ui.TextInput(
            label="成员名称 (name)",
            default=content_data.get('name', ''),
            max_length=100,
            required=True
        ))
        # Discord ID
        self.add_item(discord.ui.TextInput(
            label="Discord ID (discord_number_id)",
            default=str(self.current_data.get('discord_number_id', '')),
            max_length=20,
            required=True
        ))
        # 性格特点
        self.add_item(discord.ui.TextInput(
            label="性格特点 (personality)",
            default=content_data.get('personality', ''),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True
        ))
        # 背景信息
        self.add_item(discord.ui.TextInput(
            label="背景信息 (background)",
            default=content_data.get('background', ''),
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        ))
        # 喜好偏好
        self.add_item(discord.ui.TextInput(
            label="喜好偏好 (preferences)",
            default=content_data.get('preferences', ''),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        ))

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
                'name': updated_name,
                'discord_id': updated_discord_id,
                'personality': self.children[2].value.strip(),
                'background': self.children[3].value.strip(),
                'preferences': self.children[4].value.strip()
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
                self.item_id
            )
            
            cursor.execute(sql, params)
            conn.commit()
            log.info(f"管理员 {interaction.user.display_name} 成功更新了表 'community_members' 中 ID 为 {self.item_id} 的记录。")

            await interaction.response.send_message(f"✅ 社区成员档案 `#{self.item_id}` 已成功更新。", ephemeral=True)
            
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

# --- 编辑条目的模态窗口 ---
class EditModal(discord.ui.Modal):
    def __init__(self, db_view: 'DBView', table_name: str, item_id: str, current_data: sqlite3.Row):
        # 构造并截断标题以防止超长
        self.db_view = db_view # 修正: 将传入的 db_view 实例赋值给 self
        raw_title = self.db_view._get_entry_title(current_data)
        truncated_title = (raw_title[:30] + '...') if len(raw_title) > 30 else raw_title
        modal_title = f"编辑: {truncated_title} (#{item_id})"
        if len(modal_title) > 45:
            modal_title = modal_title[:42] + "..."
        
        super().__init__(title=modal_title)
        self.db_view = db_view
        self.table_name = table_name
        self.item_id = item_id
        self.current_data = current_data

        # 获取除 'id' 外的所有列
        columns = [col for col in self.current_data.keys() if col.lower() != 'id']

        # Discord 模态窗口最多支持5个组件
        if len(columns) > 4:
            # 这里的 self.title 赋值也会影响最终标题，所以也要截断
            base_title = f"编辑: {truncated_title} (#{item_id})"
            suffix = " (前4字段)"
            if len(base_title) + len(suffix) > 45:
                allowed_len = 45 - len(suffix) - 3 # 3 for "..."
                base_title = base_title[:allowed_len] + "..."
            self.title = base_title + suffix
            columns_to_display = columns[:4]
        else:
            columns_to_display = columns

        # 动态添加文本输入框
        for col in columns_to_display:
            value = self.current_data[col]
            # 对于 JSON 字段，美化后放入编辑框
            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
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

            self.add_item(discord.ui.TextInput(
                label=col,
                default=str(value) if value is not None else "",
                style=style,
                required=False, # 允许字段为空
            ))

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
            sql = f"UPDATE {self.table_name} SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(sql, tuple(update_values))
            conn.commit()
            log.info(f"管理员 {interaction.user.display_name} 成功更新了表 '{self.table_name}' 中 ID 为 {self.item_id} 的记录。")

            await interaction.response.send_message(f"✅ 记录 `#{self.item_id}` 已成功更新。", ephemeral=True)
            
            # --- RAG 更新 (通用) ---
            log.info(f"开始为更新后的条目 {self.item_id} (表: {self.table_name}) 同步向量数据库...")
            await incremental_rag_service.delete_entry(self.item_id)
            
            # 根据表名选择合适的处理函数
            if self.table_name == 'community_members':
                await incremental_rag_service.process_community_member(self.item_id)
            elif self.table_name == 'general_knowledge':
                await incremental_rag_service.process_general_knowledge(self.item_id)
            # 'pending_entries' 通常不直接进入 RAG，所以这里不处理
            
            log.info(f"条目 {self.item_id} 的向量数据库同步完成。")

            # 刷新原始的数据库浏览器视图
            await self.db_view.update_view()

        except sqlite3.Error as e:
            log.info(f"管理员 {interaction.user.display_name} 成功更新了表 '{self.table_name}' 中 ID 为 {self.item_id} 的记录。")
            log.error(f"更新数据库记录失败: {e}", exc_info=True)
            await interaction.response.send_message(f"更新失败: {e}", ephemeral=True)
        finally:
            conn.close()

# --- 数据库浏览器视图 ---
class DBView(discord.ui.View):
    """数据库浏览器的交互式视图"""
    
    def __init__(self, author_id: int):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.db_path = os.path.join(config.DATA_DIR, 'world_book.sqlite3')
        self.message: Optional[discord.Message] = None
        
        # --- 状态管理 ---
        self.view_mode: str = 'list'
        self.current_table: Optional[str] = None
        self.current_page: int = 0
        self.items_per_page: int = 10
        self.total_pages: int = 0
        self.current_item_id: Optional[str] = None
        self.current_list_items: List[sqlite3.Row] = []

        # 初始化时就构建好初始组件
        self._initialize_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """确保只有命令发起者才能与视图交互"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("你不能操作这个视图。", ephemeral=True)
            return False
        return True

    def _get_db_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库失败: {e}", exc_info=True)
            return None

    # --- UI 构建 ---

    def _initialize_components(self):
        """根据当前视图模式，动态构建UI组件"""
        self.clear_items()

        self.add_item(self._create_table_select())

        if self.view_mode == 'list' and self.current_table:
            self.prev_button = discord.ui.Button(label="上一页", emoji="⬅️", style=discord.ButtonStyle.secondary, disabled=self.current_page == 0)
            self.prev_button.callback = self.go_to_previous_page
            self.add_item(self.prev_button)

            self.next_button = discord.ui.Button(label="下一页", emoji="➡️", style=discord.ButtonStyle.secondary, disabled=self.current_page >= self.total_pages - 1)
            self.next_button.callback = self.go_to_next_page
            self.add_item(self.next_button)
            
            if self.current_list_items:
                self.add_item(self._create_item_select())

        elif self.view_mode == 'detail':
            self.back_button = discord.ui.Button(label="返回列表", emoji="⬅️", style=discord.ButtonStyle.secondary)
            self.back_button.callback = self.go_to_list_view
            self.add_item(self.back_button)

            self.edit_button = discord.ui.Button(label="修改", emoji="✏️", style=discord.ButtonStyle.primary)
            self.edit_button.callback = self.edit_item
            self.add_item(self.edit_button)

            self.delete_button = discord.ui.Button(label="删除", emoji="🗑️", style=discord.ButtonStyle.danger)
            self.delete_button.callback = self.delete_item
            self.add_item(self.delete_button)

    def _create_table_select(self) -> discord.ui.Select:
        """创建表格选择下拉菜单"""
        options = [
            discord.SelectOption(label="社区成员档案", value="community_members"),
            discord.SelectOption(label="通用知识", value="general_knowledge"),
        ]
        for option in options:
            if option.value == self.current_table:
                option.default = True
        
        select = discord.ui.Select(placeholder="请选择要查看的数据表...", options=options)
        select.callback = self.on_table_select
        return select

    def _create_item_select(self) -> discord.ui.Select:
        """根据当前列表页的条目创建选择菜单"""
        options = []
        for item in self.current_list_items:
            title = self._get_entry_title(item)
            label = f"{item['id']}. {title}"
            if len(label) > 100: label = label[:97] + "..."
            options.append(discord.SelectOption(label=label, value=str(item['id'])))
        
        select = discord.ui.Select(placeholder="选择一个条目查看详情...", options=options)
        select.callback = self.on_item_select
        return select

    # --- 交互处理 ---
    async def on_table_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_table = interaction.data["values"][0]
        self.current_page = 0
        self.view_mode = 'list'
        await self.update_view()

    async def on_item_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_item_id = interaction.data["values"][0]
        self.view_mode = 'detail'
        await self.update_view()

    async def go_to_list_view(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view_mode = 'list'
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

    # --- 数据操作 ---

    def _get_item_by_id(self, item_id: str) -> Optional[sqlite3.Row]:
        conn = self._get_db_connection()
        if not conn or not self.current_table: return None
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.current_table} WHERE id = ?", (item_id,))
            return cursor.fetchone()
        finally:
            if conn: conn.close()

    def _get_entry_title(self, entry: sqlite3.Row) -> str:
        """
        根据表名和数据结构，为数据库条目获取最合适的标题。
        """
        try:
            # 1. 待审核条目：标题信息在 data_json 内部
            # 1. 社区成员档案：直接使用 title 字段
            if self.current_table == 'community_members':
                return entry['title']

            # 2. 通用知识：直接使用 title 字段
            elif self.current_table == 'general_knowledge':
                return entry['title']

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning(f"解析条目 {entry['id']} 标题时出错: {e}")
            return f"ID: {entry['id']} (解析错误)"
        
        # 3. 回退机制：以防未来有其他表
        return f"ID: {entry['id']}"

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
            return await interaction.response.send_message("没有可编辑的条目。", ephemeral=True)
        
        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            return await interaction.response.send_message("找不到指定的条目。", ephemeral=True)

        # 根据表名选择不同的模态框
        if self.current_table == 'community_members':
            modal = EditCommunityMemberModal(self, self.current_item_id, current_item)
        else:
            modal = EditModal(self, self.current_table, self.current_item_id, current_item)
            
        await interaction.response.send_modal(modal)

    async def delete_item(self, interaction: discord.Interaction):
        if not self.current_item_id: return await interaction.response.send_message("没有可删除的条目。", ephemeral=True)
        item_id = self.current_item_id
        
        confirm_view = discord.ui.View(timeout=60)
        async def confirm_callback(inner_interaction: discord.Interaction):
            conn = self._get_db_connection()
            if not conn: return await inner_interaction.response.edit_message(content="数据库连接失败。", view=None)
            try:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {self.current_table} WHERE id = ?", (item_id,))
                conn.commit()
                log.info(f"管理员 {interaction.user.display_name} 删除了表 '{self.current_table}' 的记录 ID {item_id}。")
                await inner_interaction.response.edit_message(content=f"🗑️ 记录 `#{item_id}` 已被成功删除。", view=None)
                
                # --- RAG 删除 ---
                log.info(f"开始从向量数据库中删除条目 {item_id}...")
                await incremental_rag_service.delete_entry(item_id)
                log.info(f"条目 {item_id} 的向量已成功删除。")

                self.view_mode = 'list'
                conn_check = self._get_db_connection()
                if conn_check:
                    try:
                        cursor_check = conn_check.cursor()
                        cursor_check.execute(f"SELECT COUNT(*) FROM {self.current_table}")
                        total_rows = cursor_check.fetchone()[0]
                        new_total_pages = (total_rows + self.items_per_page - 1) // self.items_per_page
                        if self.current_page >= new_total_pages and self.current_page > 0:
                            self.current_page -= 1
                    finally:
                        conn_check.close()
                await self.update_view()
            except sqlite3.Error as e:
                await inner_interaction.response.edit_message(content=f"删除失败: {e}", view=None)
            finally:
                if conn: conn.close()

        async def cancel_callback(inner_interaction: discord.Interaction):
            await inner_interaction.response.edit_message(content="删除操作已取消。", view=None)

        confirm_button = discord.ui.Button(label="确认删除", style=discord.ButtonStyle.danger)
        confirm_button.callback = confirm_callback
        cancel_button = discord.ui.Button(label="取消", style=discord.ButtonStyle.secondary)
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.response.send_message(f"**⚠️ 确认删除**\n你确定要永久删除表 `{self.current_table}` 中 ID 为 `#{item_id}` 的记录吗？此操作无法撤销。", view=confirm_view, ephemeral=True)

    # --- 视图更新 ---

    async def update_view(self):
        """根据当前状态更新视图消息"""
        if not self.message:
            log.warning("DBView 尝试更新视图，但没有关联的 message 对象。")
            return

        if self.view_mode == 'list':
            embed = await self._build_list_embed()
        else:
            embed = await self._build_detail_embed()
        
        self._initialize_components()
        
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.errors.NotFound:
            log.warning(f"尝试编辑 DBView 消息失败，消息可能已被删除。")
        except discord.errors.HTTPException as e:
            log.error(f"编辑 DBView 消息时发生 HTTP 错误: {e}", exc_info=True)

    async def _build_list_embed(self) -> discord.Embed:
        conn = self._get_db_connection()
        if not conn or not self.current_table:
            return discord.Embed(title="🗂️ 数据库浏览器", description="请从下方的菜单中选择一个数据表进行查看。", color=discord.Color.blurple())

        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.current_table}")
            total_rows = cursor.fetchone()[0]
            self.total_pages = (total_rows + self.items_per_page - 1) // self.items_per_page
            offset = self.current_page * self.items_per_page
            cursor.execute(f"SELECT * FROM {self.current_table} LIMIT ? OFFSET ?", (self.items_per_page, offset))
            self.current_list_items = cursor.fetchall()

            table_name_map = {
                "community_members": "社区成员档案",
                "general_knowledge": "通用知识"
            }
            table_display_name = table_name_map.get(self.current_table, self.current_table)

            embed = discord.Embed(title=f"浏览：{table_display_name}", color=discord.Color.green())
            
            if not self.current_list_items:
                embed.description = "这个表中目前没有数据。"
            else:
                list_text = "\n".join([f"**`#{item['id']}`** - {self._get_entry_title(item)}" for item in self.current_list_items])
                embed.description = list_text
            
            embed.set_footer(text=f"第 {self.current_page + 1} / {self.total_pages or 1} 页")
            return embed
        except sqlite3.Error as e:
            log.error(f"更新数据库列表视图时出错: {e}", exc_info=True)
            return discord.Embed(title="数据库错误", description=f"加载表 `{self.current_table}` 时发生错误: {e}", color=discord.Color.red())
        finally:
            if conn:
                conn.close()

    async def _build_detail_embed(self) -> discord.Embed:
        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            self.view_mode = 'list'
            return await self._build_list_embed()

        try:
            title = self._get_entry_title(current_item)
            embed = discord.Embed(title=f"查看详情: {title}", description=f"表: `{self.current_table}` | ID: `#{self.current_item_id}`", color=discord.Color.blue())
            for col in current_item.keys():
                value = current_item[col]
                # 美化 JSON 显示
                if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                    try:
                        parsed_json = json.loads(value)
                        value = f"```json\n{json.dumps(parsed_json, indent=2, ensure_ascii=False)}\n```"
                    except json.JSONDecodeError:
                        value = f"```\n{value}\n```" # 如果不是标准JSON，也用代码块包裹
                
                # 处理空值
                if value is None or str(value).strip() == '':
                    value = "_(空)_"

                embed.add_field(name=col.replace('_', ' ').title(), value=self._truncate_field_value(value), inline=False)
            return embed
        except Exception as e:
            log.error(f"获取条目详情时出错: {e}", exc_info=True)
            return discord.Embed(title="数据库错误", description=f"加载 ID 为 {self.current_item_id} 的条目时发生错误: {e}", color=discord.Color.red())