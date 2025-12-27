from typing import TYPE_CHECKING
import discord

from .base_panel import BasePanel

if TYPE_CHECKING:
    from src.chat.features.odysseia_coin.ui.shop_ui import SimpleShopView


class ShopPanel(BasePanel["SimpleShopView"]):
    async def create_embed(self, category: str | None = None) -> discord.Embed:
        """
        创建商店的核心 Embed。
        如果提供了 category，则显示该类别下的商品提示。
        否则，显示所有商品类别列表。
        """
        description = "欢迎来到类脑商店！请选择你想要购买的商品。"
        embed = discord.Embed(
            title="类脑商店", description=description, color=discord.Color.gold()
        )

        if category:
            embed.add_field(
                name=f"📁 {category}", value="请从下拉菜单中选择商品", inline=False
            )
        else:
            if self.view.items:
                categories = sorted(
                    list(set(item["category"] for item in self.view.items))
                )
                categories_str = "\n".join([f"✨ **{cat}**" for cat in categories])
                embed.add_field(name="商品类别", value=categories_str, inline=False)
            else:
                embed.add_field(name="", value="商店暂时没有商品哦。", inline=False)

        balance_str = (
            f"{self.shop_data.balance:,}"
            if self.shop_data.balance is not None
            else "查询失败"
        )
        embed.set_footer(text=f"你的余额: {balance_str} 类脑币")
        return embed
