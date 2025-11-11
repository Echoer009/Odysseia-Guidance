import discord
import logging
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from discord.ext import commands

from src.chat.utils.database import chat_db_manager

if TYPE_CHECKING:
    from .shop_ui import SimpleShopView

log = logging.getLogger(__name__)


class LeaderboardView(discord.ui.View):
    """排行榜视图，显示类脑币和卖屁股次数排行榜"""

    def __init__(
        self, bot: commands.Bot, author: discord.Member, main_view: "SimpleShopView"
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.main_view = main_view
        self.current_page = 0
        self.leaderboard_type = "coins"  # 默认显示类脑币排行榜
        self.total_pages = 1
        self.leaderboard_data = []

        # 添加按钮
        self.add_item(CoinsLeaderboardButton())
        self.add_item(SellBodyLeaderboardButton())
        self.add_item(PreviousPageButton())
        self.add_item(NextPageButton())
        self.add_item(BackToShopButton())

        # 标记为未初始化
        self._initialized = False

    async def refresh_leaderboard(self):
        """刷新排行榜数据"""
        if self.leaderboard_type == "coins":
            self.leaderboard_data = await self.get_coin_leaderboard()
        else:
            self.leaderboard_data = await self.get_sell_body_leaderboard()

        # 计算总页数（每页10个用户，总共20个用户分2页）
        self.total_pages = max(1, (len(self.leaderboard_data) + 9) // 10)

        # 确保当前页不超出范围
        if self.current_page >= self.total_pages:
            self.current_page = max(0, self.total_pages - 1)

        # 标记为已初始化
        self._initialized = True

    async def get_coin_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取类脑币排行榜数据"""
        query = """
            SELECT user_id, balance 
            FROM user_coins 
            WHERE balance > 0 
            ORDER BY balance DESC 
            LIMIT ?
        """
        results = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (limit,), fetch="all"
        )

        leaderboard = []
        rank = 1
        for row in results:
            try:
                user = self.bot.get_user(row["user_id"])
                if user:
                    leaderboard.append(
                        {
                            "rank": rank,
                            "user_id": row["user_id"],
                            "username": user.display_name,
                            "value": row["balance"],
                        }
                    )
                    rank += 1
            except Exception as e:
                log.warning(f"获取用户 {row['user_id']} 信息失败: {e}")
                continue

        return leaderboard

    async def get_sell_body_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取卖屁股次数排行榜数据"""
        query = """
            SELECT user_id, total_sell_body_count
            FROM user_work_status
            WHERE total_sell_body_count > 0
            ORDER BY total_sell_body_count DESC
            LIMIT ?
        """
        results = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (limit,), fetch="all"
        )

        leaderboard = []
        rank = 1
        for row in results:
            try:
                user = self.bot.get_user(row["user_id"])
                if user:
                    leaderboard.append(
                        {
                            "rank": rank,
                            "user_id": row["user_id"],
                            "username": user.display_name,
                            "value": row["total_sell_body_count"],
                        }
                    )
                    rank += 1
            except Exception as e:
                log.warning(f"获取用户 {row['user_id']} 信息失败: {e}")
                continue

        return leaderboard

    async def create_leaderboard_embed(self) -> discord.Embed:
        """创建排行榜Embed"""
        # 如果还没有初始化，先初始化
        if not hasattr(self, "_initialized") or not self._initialized:
            await self.refresh_leaderboard()

        if self.leaderboard_type == "coins":
            title = "💰 类脑币排行榜"
            description = "显示拥有最多类脑币的用户"
        else:
            title = "🥵 卖屁股次数排行榜"
            description = "显示卖屁股次数最多的用户"

        embed = discord.Embed(
            title=title, description=description, color=discord.Color.gold()
        )

        # 计算当前页的数据范围
        start_idx = self.current_page * 10
        end_idx = min(start_idx + 10, len(self.leaderboard_data))
        page_data = self.leaderboard_data[start_idx:end_idx]

        if not page_data:
            embed.add_field(name="暂无数据", value="当前没有排行榜数据", inline=False)
        else:
            # 格式化排行榜数据
            leaderboard_text = ""
            for entry in page_data:
                medal = ""
                if entry["rank"] == 1:
                    medal = "🥇"
                elif entry["rank"] == 2:
                    medal = "🥈"
                elif entry["rank"] == 3:
                    medal = "🥉"
                else:
                    medal = f"#{entry['rank']}"

                value_text = f"{entry['value']}"
                if self.leaderboard_type == "coins":
                    value_text += " 类脑币"
                else:
                    value_text += " 次"

                leaderboard_text += f"{medal} **{entry['username']}**: {value_text}\n"

            embed.add_field(
                name=f"排行榜 (第 {self.current_page + 1}/{self.total_pages} 页)",
                value=leaderboard_text,
                inline=False,
            )

        embed.set_footer(text=f"第 {self.current_page + 1}/{self.total_pages} 页")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """检查交互权限"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "这不是你的排行榜界面哦！", ephemeral=True
            )
            return False
        return True


class CoinsLeaderboardButton(discord.ui.Button):
    """类脑币排行榜按钮"""

    def __init__(self):
        super().__init__(
            label="类脑币榜", style=discord.ButtonStyle.primary, emoji="💰", row=0
        )

    async def callback(self, interaction: discord.Interaction):
        """切换到类脑币排行榜"""
        self.view.leaderboard_type = "coins"
        self.view.current_page = 0
        await self.view.refresh_leaderboard()
        embed = await self.view.create_leaderboard_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)


class SellBodyLeaderboardButton(discord.ui.Button):
    """卖屁股排行榜按钮"""

    def __init__(self):
        super().__init__(
            label="卖屁股榜", style=discord.ButtonStyle.danger, emoji="🥵", row=0
        )

    async def callback(self, interaction: discord.Interaction):
        """切换到卖屁股排行榜"""
        self.view.leaderboard_type = "sell_body"
        self.view.current_page = 0
        await self.view.refresh_leaderboard()
        embed = await self.view.create_leaderboard_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)


class PreviousPageButton(discord.ui.Button):
    """上一页按钮"""

    def __init__(self):
        super().__init__(
            label="上一页", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1
        )

    async def callback(self, interaction: discord.Interaction):
        """显示上一页"""
        if self.view.current_page > 0:
            self.view.current_page -= 1
            embed = await self.view.create_leaderboard_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await interaction.response.defer()


class NextPageButton(discord.ui.Button):
    """下一页按钮"""

    def __init__(self):
        super().__init__(
            label="下一页", style=discord.ButtonStyle.secondary, emoji="➡️", row=1
        )

    async def callback(self, interaction: discord.Interaction):
        """显示下一页"""
        if self.view.current_page < self.view.total_pages - 1:
            self.view.current_page += 1
            embed = await self.view.create_leaderboard_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await interaction.response.defer()


class BackToShopButton(discord.ui.Button):
    """返回商店按钮"""

    def __init__(self):
        super().__init__(
            label="返回商店", style=discord.ButtonStyle.secondary, emoji="🏪", row=1
        )

    async def callback(self, interaction: discord.Interaction):
        """返回商店界面"""
        await interaction.response.edit_message(
            embed=self.view.main_view.create_shop_embed(), view=self.view.main_view
        )
