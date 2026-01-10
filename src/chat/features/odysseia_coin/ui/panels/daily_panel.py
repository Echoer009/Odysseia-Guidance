import discord
from src.chat.utils.database import chat_db_manager

from .base_panel import BasePanel


class DailyPanel(BasePanel):
    async def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📅 类脑娘日报",
            description="欢迎查看今日类脑娘日报！",
            color=discord.Color.blue(),
        )

        try:
            # 获取今天的模型使用数据
            usage_today = await chat_db_manager.get_model_usage_counts_today()

            if not usage_today:
                embed.add_field(
                    name="今天类脑娘回了...",
                    value="今天类脑娘还什么都没聊!",
                    inline=False,
                )
            else:
                total_replies_today = sum(row["usage_count"] for row in usage_today)

                if total_replies_today < 500:
                    comment = "今天有点安静呢，是不是大家都在忙呀？"
                elif 500 <= total_replies_today < 1000:
                    comment = "聊得不错嘛！今天也是活力满满的一天！"
                elif 1000 <= total_replies_today < 3000:
                    comment = "哇！今天是个话痨日！大家的热情像太阳一样！"
                else:
                    comment = "聊了这么多！我们是把一年的话都说完了吗？"

                stats_text = (
                    f"类脑娘今天一共回复了 **{total_replies_today}** 句话！\n"
                    f"_{comment}_"
                )

                embed.add_field(name="今日回复统计", value=stats_text, inline=False)

            # --- 获取并显示今日打工次数 ---
            total_work_count = await chat_db_manager.get_total_work_count_today()

            if total_work_count == 0:
                work_comment = "今天还没有人打工哦，是都在休息吗？"
                work_stats_text = f"_{work_comment}_"
            else:
                if total_work_count <= 10:
                    work_comment = "星星之火，可以燎原。感谢每一位打工人的贡献！"
                elif 11 <= total_work_count <= 30:
                    work_comment = (
                        "打工人的热情正在点燃社区！今天的服务器也因此充满了活力！"
                    )
                elif 31 <= total_work_count <= 60:
                    work_comment = "太惊人了！大家简直是社区建设的核心力量！"
                else:  # total_work_count > 60
                    work_comment = (
                        "这已经不是打工了，这是在建设巴别塔吧！你们的热情将成为传说！"
                    )

                work_stats_text = (
                    f"大家今天一共打工了 **{total_work_count}** 次！\n_{work_comment}_"
                )

            embed.add_field(name="社区活跃度", value=work_stats_text, inline=False)

            # --- 获取并显示今日卖屁股次数 ---
            total_sell_body_count = (
                await chat_db_manager.get_total_sell_body_count_today()
            )

            if total_sell_body_count > 0:
                if total_sell_body_count <= 5:
                    sell_body_comment = "今天也有一些勇敢的灵魂呢！"
                elif 6 <= total_sell_body_count <= 20:
                    sell_body_comment = "看来今天市场不错，大家纷纷出动！"
                else:
                    sell_body_comment = "这是……传说中的“屁股节”吗？太壮观了！"

                sell_body_stats_text = (
                    f"大家今天一共卖了 **{total_sell_body_count}** 次屁股！\n"
                    f"_{sell_body_comment}_"
                )
            else:
                sell_body_comment = "今天风平浪静，没有人出卖灵魂~"
                sell_body_stats_text = f"_{sell_body_comment}_"

            embed.add_field(name="今日特色", value=sell_body_stats_text, inline=False)

            # --- 获取并显示今日21点战绩 ---
            net_win_loss = await chat_db_manager.get_blackjack_net_win_loss_today()

            if net_win_loss > 1000:
                blackjack_comment = (
                    f"今天赢麻了！从各位赌怪身上净赚 **{net_win_loss}** 枚类脑币！"
                )
            elif net_win_loss > 0:
                blackjack_comment = (
                    f"今天运气不错，小赚了 **{net_win_loss}** 枚类脑币。明天继续！"
                )
            elif net_win_loss == 0:
                blackjack_comment = "今天赌场风平浪静，还没开张呢。"
            elif net_win_loss >= -1000:
                blackjack_comment = f"可恶！今天竟然亏了 **{-net_win_loss}** 枚类脑币！你们这些赌怪别太嚣张了！"
            else:
                blackjack_comment = f"今天要破产了呜呜呜...竟然被大家卷走了 **{-net_win_loss}** 枚类脑币！"

            embed.add_field(name="赌场风云", value=blackjack_comment, inline=False)

        except Exception as e:
            embed.add_field(
                name="数据加载失败",
                value=f"加载日报数据时出错：{e}",
                inline=False,
            )

        return embed
