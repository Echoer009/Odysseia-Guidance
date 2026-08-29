# -*- coding: utf-8 -*-
"""
运行时配置键注册表。

驱动管理后台的配置调优页面：每个条目声明键名、分组、中文标签、
中文说明和代码内的默认值。覆盖值存于 admin.config_overrides 表，
由 ConfigOverrideService 在调用点读取（默认值仍留在代码中）。
"""

from typing import Any, Dict, List

from src.chat.config.chat_config import (
    AFFECTION_CONFIG,
    API_RETRY_CONFIG,
    BLACKLIST_BAN_DURATION_MINUTES,
    CHANNEL_MEMORY_CONFIG,
    CHANNEL_MUTE_CONFIG,
    CONFESSION_CONFIG,
    CONVERSATION_MEMORY_CONFIG,
    COIN_CONFIG,
    DISABLED_INTERACTION_CHANNEL_IDS,
    FEEDING_CONFIG,
    FORUM_RAG_CONFIG,
    FORUM_RAG_MAX_DISTANCE,
    FORUM_SEARCH_DEFAULT_LIMIT,
    MAX_CONCURRENT_REQUESTS,
    MESSAGE_SETTINGS,
    PERSONAL_MEMORY_CONFIG,
    PROVIDER_RETRY_CONFIG,
    RAG_N_RESULTS_DEFAULT,
    TUTORIAL_RAG_CONFIG,
    UNRESTRICTED_CHANNEL_IDS,
    WEB_SEARCH_CONFIG,
    WORLD_BOOK_CONFIG,
    WORLD_BOOK_RAG_CONFIG,
)
from src.chat.features.games.config.blackjack_config import (
    DEALER_BET_THRESHOLDS,
    MINIMUM_BET_AMOUNTS,
    PLAYER_BET_PERCENTAGES,
)
from src.chat.features.work_game.config.work_config import WorkConfig
from src.config import (
    BOT_NAME,
    BOT_SELF_INTRODUCTION,
    COMMUNITY_NAME,
    COMMUNITY_TYPE,
    CURRENCY_NAME,
    MASCOT_TITLE,
    NICKNAME,
)

_REVIEW_CONFIG_DEFAULT = {
    "review_settings": WORLD_BOOK_CONFIG["review_settings"],
    "personal_profile_review_settings": WORLD_BOOK_CONFIG[
        "personal_profile_review_settings"
    ],
    "work_event_review_settings": WORLD_BOOK_CONFIG["work_event_review_settings"],
}

_FORUM_RAG_DEFAULT = {
    **FORUM_RAG_CONFIG,
    "MAX_DISTANCE": FORUM_RAG_MAX_DISTANCE,
    "DEFAULT_LIMIT": FORUM_SEARCH_DEFAULT_LIMIT,
}

_WORK_CONFIG_DEFAULT = {
    "event_chance": WorkConfig.EVENT_CHANCE,
    "good_event_chance": WorkConfig.GOOD_EVENT_CHANCE,
    "cooldown_hours": WorkConfig.COOLDOWN_HOURS,
    "streak_days": WorkConfig.STREAK_DAYS,
    "streak_reward": WorkConfig.STREAK_REWARD,
    "sell_body_cooldown_hours": WorkConfig.SELL_BODY_COOLDOWN_HOURS,
    "max_work_per_day": WorkConfig.MAX_WORK_PER_DAY,
    "max_sell_body_per_day": WorkConfig.MAX_SELL_BODY_PER_DAY,
}

_BLACKJACK_CONFIG_DEFAULT = {
    "player_bet_percentages": PLAYER_BET_PERCENTAGES,
    "minimum_bet_amounts": MINIMUM_BET_AMOUNTS,
    "dealer_bet_thresholds": DEALER_BET_THRESHOLDS,
}


def _e(key: str, group: str, label: str, description: str, default: Any) -> Dict:
    return {
        "key": key,
        "group": group,
        "label": label,
        "description": description,
        "default": default,
    }


CONFIG_REGISTRY: List[dict] = [
    _e(
        "identity.bot_name",
        "人设与身份",
        "Bot 名称",
        "Bot 的名字，会替换人设文本中的默认名称",
        BOT_NAME,
    ),
    _e(
        "identity.community_name",
        "人设与身份",
        "社区名称",
        "社区的名字，会替换人设文本中的默认社区名",
        COMMUNITY_NAME,
    ),
    _e(
        "identity.currency_name",
        "人设与身份",
        "货币名称",
        "金币系统的货币显示名称",
        CURRENCY_NAME,
    ),
    _e(
        "identity.mascot_title",
        "人设与身份",
        "看板娘称号",
        "Bot 在社区中的角色称号",
        MASCOT_TITLE,
    ),
    _e(
        "identity.nickname",
        "人设与身份",
        "爱称",
        "社区成员对 Bot 的爱称",
        NICKNAME,
    ),
    _e(
        "identity.community_type",
        "人设与身份",
        "社区类型",
        "社区的类型描述",
        COMMUNITY_TYPE,
    ),
    _e(
        "identity.bot_self_introduction",
        "人设与身份",
        "自我介绍",
        "Bot 的自我介绍文本",
        BOT_SELF_INTRODUCTION,
    ),
    _e(
        "affection.config",
        "好感度",
        "好感度系统配置",
        "包含触发几率、增量、每日上限、拉黑扣分和每日浮动范围",
        AFFECTION_CONFIG,
    ),
    _e(
        "economy.coin.config",
        "金币与经济",
        "金币系统配置",
        "每日首聊奖励、发帖奖励、借款上限、转账税率等",
        COIN_CONFIG,
    ),
    _e(
        "economy.work.config",
        "金币与经济",
        "打工配置",
        "打工/卖屁股的事件几率、冷却小时数、全勤奖励和每日次数上限",
        _WORK_CONFIG_DEFAULT,
    ),
    _e(
        "economy.blackjack.config",
        "金币与经济",
        "21点配置",
        "下注比例、各档最低下注金额和荷官判断阈值",
        _BLACKJACK_CONFIG_DEFAULT,
    ),
    _e(
        "feature.feeding_cooldown",
        "冷却与频率",
        "投喂冷却（秒）",
        "两次投喂之间的冷却时间（秒）",
        FEEDING_CONFIG["COOLDOWN_SECONDS"],
    ),
    _e(
        "feature.confession_cooldown",
        "冷却与频率",
        "忏悔冷却（秒）",
        "两次忏悔之间的冷却时间（秒）",
        CONFESSION_CONFIG["COOLDOWN_SECONDS"],
    ),
    _e(
        "rag.forum.config",
        "RAG与搜索",
        "论坛 RAG 配置",
        "论坛混合搜索的召回数量、RRF 常数、精确匹配加分和距离阈值",
        _FORUM_RAG_DEFAULT,
    ),
    _e(
        "rag.tutorial.config",
        "RAG与搜索",
        "教程 RAG 配置",
        "教程知识库混合搜索的召回与融合参数（重启后生效）",
        TUTORIAL_RAG_CONFIG,
    ),
    _e(
        "rag.worldbook.config",
        "RAG与搜索",
        "世界书 RAG 配置",
        "世界书混合搜索的召回与融合参数（重启后生效）",
        WORLD_BOOK_RAG_CONFIG,
    ),
    _e(
        "rag.conversation_memory.config",
        "RAG与搜索",
        "对话记忆配置",
        "永久对话记忆的分块大小、检索数量与距离阈值",
        CONVERSATION_MEMORY_CONFIG,
    ),
    _e(
        "rag.channel_memory.config",
        "RAG与搜索",
        "频道记忆配置",
        "频道上下文历史的拉取与格式化条数",
        CHANNEL_MEMORY_CONFIG,
    ),
    _e(
        "rag.n_results_default",
        "RAG与搜索",
        "世界书默认召回条数",
        "聊天时世界书 RAG 搜索的默认返回条数",
        RAG_N_RESULTS_DEFAULT,
    ),
    _e(
        "websearch.config",
        "RAG与搜索",
        "联网搜索配置",
        "SearXNG 地址、结果数量、超时与频率限制（重启后生效）",
        WEB_SEARCH_CONFIG,
    ),
    _e(
        "reply.dm_threshold",
        "回复行为",
        "长回复转私信阈值",
        "回复超过此字符数时改为私信发送（豁免频道除外）",
        MESSAGE_SETTINGS["DM_THRESHOLD"],
    ),
    _e(
        "ai.provider_retry_config",
        "AI稳定性",
        "Provider 重试配置",
        "故障转移前对同一 Provider 的最大重试次数与重试间隔",
        PROVIDER_RETRY_CONFIG,
    ),
    _e(
        "channels.disabled_interaction_ids",
        "频道与权限",
        "交互禁用频道",
        "在这些频道中禁用所有 Bot 交互（@提及与命令）",
        list(DISABLED_INTERACTION_CHANNEL_IDS),
    ),
    _e(
        "channels.unrestricted_ids",
        "频道与权限",
        "限制豁免频道",
        "在这些频道中解除长回复私聊、闭嘴命令和忏悔可见性限制",
        sorted(UNRESTRICTED_CHANNEL_IDS),
    ),
    _e(
        "mute.vote_config",
        "活动与审核",
        "禁言投票配置",
        "禁言投票的通过票数、投票时长和禁言时长（分钟）",
        CHANNEL_MUTE_CONFIG,
    ),
    _e(
        "warning.ban_duration_minutes",
        "活动与审核",
        "拉黑封禁时长（分钟）",
        "文爱检测触发封禁的时长范围 [最小, 最大]（分钟）",
        list(BLACKLIST_BAN_DURATION_MINUTES),
    ),
    _e(
        "review.config",
        "活动与审核",
        "审核系统配置",
        "世界书、个人资料与打工事件的审核时长和票数阈值",
        _REVIEW_CONFIG_DEFAULT,
    ),
]
