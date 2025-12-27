import discord

from .base_panel import BasePanel


class MainPanel(BasePanel):
    async def create_embed(self) -> discord.Embed:
        balance_str = (
            f"{self.shop_data.balance:,}"
            if self.shop_data.balance is not None
            else "查询失败"
        )

        embed = discord.Embed(
            title="🧠 类脑商店",
            description=f"欢迎来到类脑商店，{self.view.user.mention}！\n"
            f"你的当前余额: **{balance_str}** 类脑币",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="使用下面的菜单浏览商店。")
        return embed
