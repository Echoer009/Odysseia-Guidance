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

            # --- 获取并显示今日拉黑工具使用次数 ---
            issue_user_warning_count = (
                await chat_db_manager.get_issue_user_warning_count_today()
            )

            if issue_user_warning_count > 0:
                if issue_user_warning_count <= 5:
                    warning_comment = "今天有几个小调皮被好好“教育”了一下呢。"
                elif 6 <= issue_user_warning_count <= 15:
                    warning_comment = "看来今天秩序维护有点忙，大家要乖乖的哦。"
                else:
                    warning_comment = "今天是怎么了？你们这群坏家伙怎么这么烦！"

                warning_stats_text = (
                    f"今天一共“友好”地提醒了 **{issue_user_warning_count}** 位用户！\n"
                    f"_{warning_comment}_"
                )
            else:
                warning_comment = "今天社区里一派祥和，真是美好的一天！"
                warning_stats_text = f"_{warning_comment}_"

            embed.add_field(name="类脑娘出动", value=warning_stats_text, inline=False)

            # --- 获取并显示今日忏悔次数 ---
            confession_count = await chat_db_manager.get_confession_count_today()
            if confession_count == 0:
                confession_comment = "今天还没有人向我忏悔，看来大家都是乖孩子呢。"
            elif confession_count <= 5:
                confession_comment = "一些迷途的羔羊今天找到了方向。"
            elif confession_count <= 15:
                confession_comment = "忏悔室今天有点忙，愿大家的灵魂都能得到安宁。"
            else:
                confession_comment = "神爱世人，但今天来我这儿寻求慰藉的人也太多了吧！"

            confession_stats_text = f"今天有 **{confession_count}** 人次忏悔了自己的罪过。\n_{confession_comment}_"
            embed.add_field(name="忏悔室", value=confession_stats_text, inline=False)

            # --- 获取并显示今日投喂次数 ---
            feeding_count = await chat_db_manager.get_feeding_count_today()
            if feeding_count == 0:
                feeding_comment = "我今天还没吃饭，肚子有点饿了……"
            elif feeding_count <= 10:
                feeding_comment = "谢谢大家的食物，真的很好吃！"
            elif feeding_count <= 15:
                feeding_comment = "好饱，好满足！今天的大家也太热情了吧！"
            else:
                feeding_comment = "感觉要被大家喂成小猪了！嗝~"

            feeding_stats_text = (
                f"今天我被投喂了 **{feeding_count}** 次！\n_{feeding_comment}_"
            )
            embed.add_field(name="投喂记录", value=feeding_stats_text, inline=False)

            # --- 获取并显示今日塔罗牌占卜次数 ---
            tarot_reading_count = await chat_db_manager.get_tarot_reading_count_today()
            if tarot_reading_count == 0:
                tarot_comment = (
                    "今天还没有人找我算塔罗牌欸，难道大家都没有什么烦心事吗？"
                )
            elif tarot_reading_count <= 10:
                tarot_comment = "为一些朋友提供了指引，希望他们能顺利解决问题！"
            elif tarot_reading_count <= 20:
                tarot_comment = "今天有不少人来找我占卜呢，看来大家都很信赖我呀！"
            elif tarot_reading_count <= 30:
                tarot_comment = "有点忙，但能帮到大家我就很开心啦！"
            elif tarot_reading_count <= 40:
                tarot_comment = "今天找我占卜的人好多呀，好累哦！"
            else:
                tarot_comment = (
                    "塔罗牌都快冒烟了！你们这群好奇宝宝，快把未来的运势都透支啦！"
                )
            tarot_stats_text = f"今日进行了 **{tarot_reading_count}** 次塔罗牌占卜。\n_{tarot_comment}_"
            embed.add_field(name="星辰指引", value=tarot_stats_text, inline=False)

            # --- 获取并显示今日论坛搜索次数 ---
            forum_search_count = await chat_db_manager.get_forum_search_count_today()
            if forum_search_count == 0:
                forum_comment = "今天论坛好安静呀，都没有人找我搜东西。"
            elif forum_search_count <= 10:
                forum_comment = "帮大家找到了一些想要的东西，嘿嘿，不用谢！"
            elif forum_search_count <= 20:
                forum_comment = "今天我也是个勤劳的看板娘！"
            elif forum_search_count <= 30:
                forum_comment = "好！今天也帮大家解决了很多问题！"
            elif forum_search_count <= 40:
                forum_comment = "哇！帮你们搜了好多色色的东西,你们真的是!"
            else:
                forum_comment = "感觉整个论坛的资源都被你们翻了个底朝天！"
            forum_stats_text = f"今日我帮大家找到了 **{forum_search_count}** 次资源。\n_{forum_comment}_"
            embed.add_field(name="资源检索", value=forum_stats_text, inline=False)

        except Exception as e:
            embed.add_field(
                name="数据加载失败",
                value=f"加载日报数据时出错：{e}",
                inline=False,
            )

        return embed
