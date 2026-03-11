from discord.ui import Button, Select
from discord import SelectOption, Interaction
from typing import List, Coroutine, Callable


class PaginatedSelect:
    """
    一个帮助类，用于创建和管理分页的下拉选择菜单。
    当选项超过25个时，它会自动创建多个Select菜单，并提供翻页按钮。
    """

    def __init__(
        self,
        placeholder: str,
        custom_id_prefix: str,
        options: List[SelectOption],
        on_select_callback: Callable[[Interaction, List[str]], Coroutine],
        label_prefix: str,
    ):
        self.placeholder = placeholder
        self.custom_id_prefix = custom_id_prefix
        self.options = options
        self.on_select_callback = on_select_callback
        self.label_prefix = label_prefix
        self.current_page = 0
        self.pages = (
            [self.options[i : i + 25] for i in range(0, len(self.options), 25)]
            if self.options
            else [[]]
        )

    def create_select(self, row: int = 0) -> Select:
        """根据当前页面创建Select组件。"""
        page_text = (
            f" (第 {self.current_page + 1}/{len(self.pages)} 页)"
            if len(self.pages) > 1
            else ""
        )
        select = Select(
            placeholder=f"{self.placeholder}{page_text}",
            options=self.pages[self.current_page]
            if self.pages[self.current_page]
            else [SelectOption(label="无可用选项", value="disabled", default=True)],
            custom_id=f"{self.custom_id_prefix}_{self.current_page}",
            disabled=not self.pages[self.current_page],
            row=row,
        )

        # 创建一个包装回调，将 interaction 传递给 on_select_callback
        # 并从 interaction.data 中提取 values
        async def _callback_wrapper(interaction: Interaction):
            values = []
            if interaction.data and isinstance(interaction.data, dict):
                values = interaction.data.get("values", [])
            await self.on_select_callback(interaction, values)

        select.callback = _callback_wrapper
        return select

    def get_buttons(self, row: int = 0) -> List[Button]:
        """获取带明确标签的翻页按钮。"""
        buttons = []
        if len(self.pages) > 1:
            buttons.append(
                Button(
                    label=f"{self.label_prefix} 上一页",
                    custom_id=f"{self.custom_id_prefix}_prev",
                    disabled=self.current_page == 0,
                    row=row,
                )
            )
            buttons.append(
                Button(
                    label=f"{self.label_prefix} 下一页",
                    custom_id=f"{self.custom_id_prefix}_next",
                    disabled=self.current_page == len(self.pages) - 1,
                    row=row,
                )
            )
        return buttons

    def handle_pagination(self, custom_id: str) -> bool:
        """处理分页按钮的点击事件。"""
        if custom_id == f"{self.custom_id_prefix}_next":
            if self.current_page < len(self.pages) - 1:
                self.current_page += 1
                return True
        elif custom_id == f"{self.custom_id_prefix}_prev":
            if self.current_page > 0:
                self.current_page -= 1
                return True
        return False
