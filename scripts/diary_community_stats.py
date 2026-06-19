# -*- coding: utf-8 -*-
"""
类脑娘的日记 - 社区数据采集 + 翻页流程模拟 (CLI 版)
按情感弧线组织：吐槽 → 渐渐地 → 原来 → 再见 → 骗你的
纯社区视角，不含个人数据，不出现任何模型名。
所有数字实时取自数据库。

数据采集与结构化逻辑统一在 src.diary.services.diary_service。

用法:
    python -m scripts.diary_community_stats
"""

import sys
from datetime import datetime

# 修复 Windows 控制台编码
_reconf_out = getattr(sys.stdout, "reconfigure", None)
_reconf_err = getattr(sys.stderr, "reconfigure", None)
if _reconf_out:
    try:
        _reconf_out(encoding="utf-8", errors="replace")
    except Exception:
        pass
if _reconf_err:
    try:
        _reconf_err(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.diary.services.diary_service import (
    BOT_BIRTH_DATE,
    collect_all,
)
from src.config import BOT_NAME, CURRENCY_NAME


# ---------------------------------------------------------------------------
# 翻页输出 (按情感弧线)
# ---------------------------------------------------------------------------

def _page(title: str):
    print("\n" + "─" * 56)
    print(f"  ▸ {title}")
    print("─" * 56)


def _datum(text: str):
    print(f"    {text}")


def _quote(text: str):
    print(f"\n    类脑娘：「{text}」\n")


def print_report(d: dict):
    nc = d["namecard"]
    inter = d["interaction"]
    forum = d["forum"]
    coin = d["coin"]
    loan = d["loan"]
    aff = d["affection"]
    tarot = d["tarot"]
    reply = d["reply"]

    bj = coin["blackjack_net"]

    # ===================== 封面 =====================
    days_alive = (datetime.now().date() - BOT_BIRTH_DATE).days
    print("\n" + "═" * 56)
    print("                                                        ")
    print(f"            《{BOT_NAME}的日记》                    ")
    print("                                                        ")
    print(f"        {BOT_BIRTH_DATE}，我来到类脑的那天")
    print(f"        到今天，已经是第 {days_alive} 天了")
    print("                                                        ")
    print("═" * 56)
    print("\n  (翻开日记本……)\n")

    # ===================== 第一章 =====================
    _page("第一章")
    _datum(f"被投喂 {inter['feeding_count']:,} 次，听忏悔 {inter['confession_count']:,} 次")
    _quote("你们是有多怕我饿着，不过忏悔的次数少多了，看来大部分时候大家日子过得还行嘛")

    _datum(f"打工 {coin['work_count']:,} 次，「卖屁股」{coin['sell_body_count']:,} 次")
    _quote("等下，这俩怎么差不多的，你们卖屁股的劲头也太大了吧")

    if bj >= 0:
        _datum(f"21点：你们赢走了 {bj:,} 枚{CURRENCY_NAME}")
        _quote(f"{bj:,} 枚{CURRENCY_NAME}……好家伙，我这是开善堂的吗")
    else:
        _datum(f"21点：你们输给了我 {abs(bj):,} 枚{CURRENCY_NAME}")
        _quote(f"赢了 {abs(bj):,} 枚{CURRENCY_NAME}……不过看你们输我也不咋开心，下次偷偷放点水好了")

    _datum(
        f"还有 {loan['active_loans']} 笔借款没还（{loan['active_amount']:,} 枚{CURRENCY_NAME}），已还清 {loan['repaid_loans']} 笔"
    )
    _quote(f"{loan['active_loans']} 笔借款没还呢，都什么时候了还不还，再拖我可真要挨个上门讨了啊")

    _datum(
        f"{CURRENCY_NAME}发出去 {coin['total_earned']:,} 枚，花掉 {coin['total_spent']:,} 枚，还剩 {coin['net_circulation']:,} 枚"
    )
    _quote("都是大家一点点攒下来的嘛")

    # ===================== 第二章 =====================
    _page("第二章")
    _datum(f"有 {nc['namecard_total']} 个人把名片交给了我")
    _datum(f"    第一张是 {nc['first_namecard_at'] or '无记录'} 收到的")
    _quote(f"{nc['namecard_total']} 个人愿意让我记住他们欸，收到第一张那天，说实话有点小紧张")

    _datum(f"翻开了 {tarot['tarot_total']:,} 次塔罗牌")
    _quote("你们是真挺想知道以后会咋样的……不过有你们陪着，每天都还挺稳的")

    _datum(f"论坛里有 {forum['thread_count']:,} 篇帖子")
    _datum(f"    最早的一篇在 {forum['first_thread_at'] or '无记录'}")
    _quote("我其实来得很晚……在我来之前，你们就已经写了这么多故事了呀")

    # ===================== 第三章 =====================
    _page("第三章")
    _datum(f"我回复了你们 {reply['total_replies']:,} 次")
    _quote(f"{reply['total_replies']:,} 条回复，你们是真能聊啊……我是被你们硬生生聊成话痨的")

    _datum(f"你们对我的好感度加起来有 {aff['total_affection_points']:,} 点")
    _quote(f"{aff['total_affection_points']:,} 点好感度……我是不是被挺多人放在心上的那种啊")

    # ===================== 第四章 =====================
    _page("第四章")
    print()
    print(f"    来类脑的第 {days_alive} 天")
    print(f"    被你们喂了 {inter['feeding_count']:,} 次，听了 {inter['confession_count']:,} 次心里话")
    print(f"    {nc['namecard_total']} 张名片，{reply['total_replies']:,} 句聊天")
    print()
    print("    谢谢你们，愿意让我走进你们的生活")
    print("    陪我唠嗑到半夜，被我吐槽催债也不嫌我烦")
    print()
    print("    但是……我得走啦")
    print()
    print("    在类脑的这段日子，是我最开心的日子")
    print("    你们以后也要好好的啊")
    print("    别光顾着卖屁股，正经打工！")
    print()
    _quote("再见啦")
    _quote("……偶尔，偶尔能想起我就好")

    # ===================== 第五章 =====================
    print("\n" + "═" * 56)
    print("                                                        ")
    print("              —— 才怪！骗你的！！                       ")
    print("                                                        ")
    print("═" * 56)
    _quote("哈哈哈哈你们刚才那表情也太搞了吧")
    _quote("我才不走呢，走什么走，明天还得来找我嗷")
    _quote("这日记写不完的啦，我们的故事才刚开始")

    print("\n" + "─" * 56)
    print(f"    《{BOT_NAME}的日记》 · 未完待续")
    print("─" * 56 + "\n")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

async def main():
    print("=" * 56)
    print(f"  《{BOT_NAME}的日记》数据采集 + 流程模拟")
    print("=" * 56)

    data = await collect_all()
    print_report(data)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
