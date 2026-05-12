import discord
import logging
import random
from typing import Dict, Any, List

from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.services.faction_service import faction_service

log = logging.getLogger(__name__)


class EventPanelView(discord.ui.View):
    """
    活动的主界面，实现了派系和奉献行为之间的联动选择。
    """

    def __init__(self, event_data: Dict[str, Any], main_shop_view: discord.ui.View):
        super().__init__(timeout=180)
        self.event_data = event_data
        self.main_shop_view = main_shop_view
        self.faction_service = faction_service

        # State tracking
        self.selected_faction_id: str | None = None
        self.selected_item_id: str | None = None

        self.create_view()

    def create_view(self):
        """动态创建视图组件。"""
        self.clear_items()

        factions = self.event_data.get("factions", [])
        items = self.event_data.get("items", {})

        # 1. Faction Selection
        self.add_item(FactionSelect(factions))

        # 2. Item Selection (initially disabled)
        self.add_item(EventItemSelect(items, disabled=True))

        # 3. Purchase Button
        self.add_item(EventPurchaseButton(disabled=True))

        # 4. Back Button
        back_button = discord.ui.Button(
            label="返回商店", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )
        back_button.callback = self.back_to_shop_callback
        self.add_item(back_button)

    async def update_view(self, interaction: discord.Interaction):
        """
        Central method to update the view's components based on the current state.
        """
        # Find components
        item_select = next(
            (item for item in self.children if isinstance(item, EventItemSelect)), None
        )
        purchase_button = next(
            (item for item in self.children if isinstance(item, EventPurchaseButton)),
            None,
        )

        if not (item_select and purchase_button):
            return  # Should not happen

        # Update and enable item select if a faction is chosen
        if self.selected_faction_id:
            item_select.update_options(self.selected_faction_id)
            item_select.disabled = False
        else:
            item_select.placeholder = "请先选择一个阵营"
            item_select.options.clear()
            item_select.options.append(
                discord.SelectOption(label="...", value="placeholder", emoji="❓")
            )
            item_select.disabled = True

        # Enable purchase button only if an item is selected
        purchase_button.disabled = self.selected_item_id is None

        await interaction.response.edit_message(view=self)

    async def create_event_embed(self) -> discord.Embed:
        """创建活动主界面的 Embed，兼具美观和信息。"""
        event_name = self.event_data.get("event_name", "特别活动")
        description = self.event_data.get("description", "欢迎来到活动！")
        panel_config = self.event_data.get("entry_panel", {})

        embed = discord.Embed(
            title=f"🎃 {event_name} 🎃",
            description=f"*{description}*",
            color=discord.Color.orange(),
        )

        if panel_config.get("thumbnail_url"):
            embed.set_thumbnail(url=panel_config["thumbnail_url"])

        # 添加排行榜
        leaderboard = await self.faction_service.get_faction_leaderboard()
        leaderboard_text = ""
        if leaderboard:
            faction_map = {
                f["faction_id"]: f["faction_name"]
                for f in self.event_data.get("factions", [])
            }
            rank_emojis = ["🥇", "🥈", "🥉"]
            for i, entry in enumerate(leaderboard):
                rank_emoji = rank_emojis[i] if i < len(rank_emojis) else "🔹"
                faction_name = faction_map.get(entry["faction_id"], entry["faction_id"])
                leaderboard_text += (
                    f"{rank_emoji} **{faction_name}**: {entry['total_points']} 点贡献\n"
                )
        else:
            leaderboard_text = "👻 各大派系仍在暗中积蓄力量...快来打响第一枪！"

        embed.add_field(name="🏆 实时阵营榜", value=leaderboard_text, inline=False)

        embed.add_field(
            name="👇 如何参与",
            value="1. 选择你的`所属阵营`。\n"
            "2. 选择具体的`奉献行为`。\n"
            "3. 点击`确认奉献`为你选择的阵营贡献力量！",
            inline=False,
        )

        embed.set_footer(text="夜幕已至，选择你的命运吧...")
        return embed

    async def back_to_shop_callback(self, interaction: discord.Interaction):
        """点击"返回商店"按钮的回调。"""
        embeds_to_send = []
        event_promo_embed = await self.create_event_embed()
        embeds_to_send.append(event_promo_embed)
        shop_embed = self.main_shop_view.create_shop_embed()  # type: ignore[attr-defined]
        embeds_to_send.append(shop_embed)
        await interaction.response.edit_message(
            embeds=embeds_to_send, view=self.main_shop_view
        )


class FactionSelect(discord.ui.Select):
    """派系信息选择下拉菜单"""

    def __init__(self, factions: List[Dict[str, Any]]):
        options = [
            discord.SelectOption(
                label=f"阵营: {f['faction_name']}",
                value=f["faction_id"],
                description=f["description"][:100],
                emoji=f.get("icon"),
            )
            for f in factions
        ]
        super().__init__(
            placeholder="第一步: 选择你的所属阵营...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        assert isinstance(view, EventPanelView)
        view.selected_faction_id = self.values[0]
        view.selected_item_id = None  # Reset item
        await view.update_view(interaction)


class EventItemSelect(discord.ui.Select):
    """奉献行为选择下拉菜单 (动态更新)"""

    def __init__(self, all_items: Dict[str, Any], disabled: bool = True):
        self.all_items = all_items
        initial_options = [
            discord.SelectOption(label="...", value="placeholder", emoji="❓")
        ]
        super().__init__(
            placeholder="第二步: 选择奉献行为...",
            min_values=1,
            max_values=1,
            options=initial_options,
            disabled=disabled,
        )

    def update_options(self, faction_id: str):
        """根据所选派系，动态更新选项，并按价格排序。"""
        self.options.clear()
        items_for_faction = self.all_items.get(faction_id, {})

        all_items = []
        for level, items in items_for_faction.items():
            all_items.extend(items)

        # 按价格排序
        all_items.sort(key=lambda x: x.get("price", 0))

        if not all_items:
            self.placeholder = "该阵营下没有可用的奉献行为"
            self.options.append(
                discord.SelectOption(label="...", value="placeholder", emoji="❓")
            )
            return

        self.placeholder = "第二步: 选择具体的奉献行为..."
        for item in all_items:
            self.options.append(
                discord.SelectOption(
                    label=item["item_name"],
                    value=item["item_id"],
                    description=f"{item['price']} 类脑币 - {item['description']}"[:100],
                    emoji="💖",
                )
            )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        assert isinstance(view, EventPanelView)
        view.selected_item_id = self.values[0]
        await view.update_view(interaction)


class EventPurchaseButton(discord.ui.Button):
    """奉献确认按钮"""

    def __init__(self, disabled: bool = True):
        super().__init__(
            label="确认奉献",
            style=discord.ButtonStyle.success,
            emoji="💰",
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        assert isinstance(view, EventPanelView)
        if not all(
            [
                view.selected_faction_id,
                view.selected_item_id,
            ]
        ):
            await interaction.response.send_message(
                "请确保已选择阵营和具体的奉献行为！", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Find the selected item from the nested dictionary
        faction_items = view.event_data["items"].get(view.selected_faction_id, {})
        selected_item = None
        for level, items in faction_items.items():
            found_item = next(
                (item for item in items if item["item_id"] == view.selected_item_id),
                None,
            )
            if found_item:
                selected_item = found_item
                break

        if not selected_item:
            await interaction.followup.send("选择的奉献行为无效。", ephemeral=True)
            return

        # 1. Handle the purchase via coin_service
        success, message, _ = await coin_service.purchase_event_item(
            user_id=interaction.user.id,
            item_name=selected_item["item_name"],
            price=selected_item["price"],
        )

        if not success:
            await interaction.followup.send(message, ephemeral=True)
            return

        # 2. Determine points (handle gacha)
        points_to_add = 0
        if "points" in selected_item:
            points_to_add = selected_item["points"]
        elif "points_range" in selected_item:
            points_range = selected_item["points_range"]
            points_to_add = random.randint(points_range[0], points_range[1])

        if points_to_add == 0:
            await interaction.followup.send(
                "此行为不增加贡献点，但你的心意她已收到。", ephemeral=True
            )
            return

        # 3. Add points to the faction
        try:
            assert view.selected_faction_id is not None
            await view.faction_service.add_points_to_faction(
                user_id=interaction.user.id,
                item_id=selected_item["item_id"],
                points_to_add=points_to_add,
                faction_id=view.selected_faction_id,
            )
        except Exception as e:
            log.error(
                f"Failed to add points for user {interaction.user.id} after purchase: {e}"
            )
            await interaction.followup.send(
                "奉献成功，但在为你支持的派系增加贡献时发生错误！请联系管理员。",
                ephemeral=True,
            )
            return

        # 4. Send success message and refresh the main view
        faction_name = next(
            f["faction_name"]
            for f in view.event_data["factions"]
            if f["faction_id"] == view.selected_faction_id
        )

        success_message = f"你的奉献已被感知！你成功为 **{faction_name}** 阵营贡献了 **{points_to_add}** 点！"
        # 从 item_id 中提取奉献等级
        dedication_level = (
            view.selected_item_id.split("_")[1] if view.selected_item_id else ""
        )
        if dedication_level == "gacha":
            success_message += " (来自命运的随机祝福)"

        await interaction.followup.send(success_message, ephemeral=True)

        # Refresh the original message with the updated leaderboard
        new_embed = await view.create_event_embed()
        await interaction.edit_original_response(embed=new_embed, view=view)
