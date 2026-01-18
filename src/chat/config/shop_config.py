# -*- coding: utf-8 -*-

"""
商店商品配置文件
用于定义商店中所有商品的详细信息和价格。
"""

from src.chat.features.odysseia_coin.service.coin_service import (
    PERSONAL_MEMORY_ITEM_EFFECT_ID,
    WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID,
    COMMUNITY_MEMBER_UPLOAD_EFFECT_ID,
    DISABLE_THREAD_COMMENTOR_EFFECT_ID,
    BLOCK_THREAD_REPLIES_EFFECT_ID,
    ENABLE_THREAD_COMMENTOR_EFFECT_ID,
    ENABLE_THREAD_REPLIES_EFFECT_ID,
    SELL_BODY_EVENT_SUBMISSION_EFFECT_ID,
    CLEAR_PERSONAL_MEMORY_ITEM_EFFECT_ID,
    VIEW_PERSONAL_MEMORY_ITEM_EFFECT_ID,
)

SHOP_ITEMS = [
    # name, description, price, category, target, effect_id
    (
        "枯萎向日葵",
        "购买后类脑娘不会再暖你的帖子",
        0,
        "物品-给自己",
        "self",
        DISABLE_THREAD_COMMENTOR_EFFECT_ID,
    ),
    (
        "告示牌",
        "上面写着禁止通行,购买后类脑娘不会在你的帖子下面对话",
        0,
        "物品-给自己",
        "self",
        BLOCK_THREAD_REPLIES_EFFECT_ID,
    ),
    (
        "魔法向日葵",
        "神奇的魔法向日葵!购买后类脑娘又会暖你的帖子了,友谊的魔法!。",
        10,
        "物品-给自己",
        "self",
        ENABLE_THREAD_COMMENTOR_EFFECT_ID,
    ),
    (
        "通行许可",
        "一张官方签发的许可,购买后类脑娘可以在你的帖子下对话.并且可以设置类脑娘的活跃时间哦",
        10,
        "物品-给自己",
        "self",
        ENABLE_THREAD_REPLIES_EFFECT_ID,
    ),
    (
        "名片",
        "输入你的信息,并解锁与类脑娘的专属长期记忆,让她真正地记住你。",
        100,
        "物品-给自己",
        "self",
        PERSONAL_MEMORY_ITEM_EFFECT_ID,
    ),
    (
        "黑衣人的记忆消除器",
        "“看这里。”咔嚓一声，一道闪光之后，类脑娘会忘记所有关于你的个人记忆。别担心，这玩意不防墨镜，但也许能防止你社会性死亡。",
        500,
        "物品-给自己",
        "self",
        CLEAR_PERSONAL_MEMORY_ITEM_EFFECT_ID,
    ),
    (
        "午后闲谈",
        "阳光正好，不如和她闲聊一会儿？她会告诉你，在你们相处的这段时间里，她悄悄记下的，关于你的那些印象与回忆。",
        50,
        "物品-给自己",
        "self",
        VIEW_PERSONAL_MEMORY_ITEM_EFFECT_ID,
    ),
    (
        "知识纸条",
        "写下你对社区的了解（仅限无关社区成员的信息），帮助类脑娘更好地认识世界。",
        0,
        "物品-贡献",
        "self",
        WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID,
    ),
    (
        "社区成员档案上传",
        "上传其他社区成员的档案信息，上传的信息将被正确识别为社区成员。",
        100,
        "物品-贡献",
        "self",
        COMMUNITY_MEMBER_UPLOAD_EFFECT_ID,
    ),
    (
        "拉皮条",
        "给卖屁股的大家提供更多工作机会吧!",
        0,
        "物品-贡献",
        "self",
        SELL_BODY_EVENT_SUBMISSION_EFFECT_ID,
    ),
    ("草莓小蛋糕", "精致的奶油草莓蛋糕", 15, "食品-给类脑娘", "ai", None),
    ("巧克力曲奇", "香浓可口的巧克力曲奇饼干", 12, "食品-给类脑娘", "ai", None),
    ("抹茶马卡龙", "精致的法式抹茶马卡龙", 18, "食品-给类脑娘", "ai", None),
    ("布丁", "滑嫩香甜的焦糖布丁", 10, "食品-给类脑娘", "ai", None),
    ("水果沙拉", "新鲜多样的水果拼盘", 8, "食品-给类脑娘", "ai", None),
    ("向日葵", "代表阳光的花朵,不觉得和类脑娘很配吗?", 8, "礼物-给类脑娘", "ai", None),
    ("泰迪熊", "承载着回忆的泰迪熊", 20, "礼物-给类脑娘", "ai", None),
    ("明信片", "旅途中随手买的明信片", 3, "礼物-给类脑娘", "ai", None),
    ("星空投影灯", "可以投射美丽星空的夜灯", 25, "礼物-给类脑娘", "ai", None),
    ("音乐盒", "播放轻柔音乐的精美音乐盒", 30, "礼物-给类脑娘", "ai", None),
]
