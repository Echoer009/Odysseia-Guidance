# -*- coding: utf-8 -*-
"""
年度总结工具 - 回顾这一年在类脑社区的点点滴滴
"""

import logging
import discord
from typing import Dict, Any
from datetime import datetime
from collections import Counter

from pydantic import BaseModel

from src.chat.utils.database import chat_db_manager
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)
from src.chat.utils.message_utils import safe_send
from src import config as app_config
from src.chat.features.tools.tool_metadata import tool_metadata
from src.database.database import AsyncSessionLocal
from src.database.models import (
    CoinTransaction,
    InteractionLog,
    UserAffection,
    CommunityMemberProfile,
)
from sqlalchemy import select, func, and_

log = logging.getLogger(__name__)


class YearlySummaryParams(BaseModel):
    """年度总结参数（无需参数）"""

    pass


@tool_metadata(
    name="年度总结",
    description="回顾这一年在类脑社区的点点滴滴，生成个性化年度报告",
    emoji="🎉",
    category="总结",
)
async def get_yearly_summary(**kwargs) -> Dict[str, Any]:
    """
    为当前用户生成年度活动总结报告并通过私信发送。
    无需任何参数，系统自动识别用户身份。
    """
    # 步骤 1: 验证并获取 user_id
    # 核心安全保障：user_id 必须从 kwargs 中由系统注入。
    user_id_str = kwargs.get("user_id")
    if not user_id_str:
        log.error("安全错误：get_yearly_summary 未能从 tool_service 接收到 user_id。")
        return {
            "status": "error",
            "message": "哎呀，内部出现了一点小问题，没能定位到你的身份。",
        }

    # 强制将user_id转换为整数，以防止模型传入浮点数或科学记数法导致错误
    user_id = int(user_id_str)

    # 步骤 2: 执行核心逻辑
    year = 2025
    log.info(f"--- [工具执行]: get_yearly_summary, user_id={user_id}, year={year} ---")

    # 延迟导入以避免循环依赖
    from src.chat.services.ai.service import ai_service

    # 1. 检查用户是否已经生成过当年的总结
    # 1. 检查用户生成次数是否已达上限
    status_result = await _check_summary_status(user_id, year)
    generation_count = status_result.get("count", 0)
    generation_limit = 3

    if generation_count >= generation_limit:
        log.info(
            f"用户 {user_id} 在 {year} 年的总结生成次数已达上限 {generation_limit} 次，操作终止。"
        )
        message = f"你今年的 {year} 年度总结生成次数已经用完啦（最多 {generation_limit} 次）。"
        return {"status": "limit_reached", "message": message}

    # 2. 获取 Discord 用户对象以便发送私信
    if not ai_service.bot:
        log.error("Bot 实例尚未注入AIService，无法发送年度总结。")
        return {"status": "error", "message": "机器人核心服务异常，暂时无法生成总结。"}

    try:
        user = await ai_service.bot.fetch_user(user_id)
    except discord.NotFound:
        log.warning(f"无法找到 ID 为 {user_id} 的用户，无法发送年度总结。")
        return {"status": "error", "message": "似乎找不到你这位用户了呢。"}
    except discord.HTTPException as e:
        log.error(f"获取用户 {user_id} 时发生网络错误: {e}")
        return {"status": "error", "message": "在查找你的用户信息时网络好像开小差了。"}

    # 3. 获取总结数据并判断层级
    summary_data = await _get_user_summary_data(user_id, year)
    if not summary_data:
        return {"status": "error", "message": "获取你的年度数据时遇到了麻烦。"}

    tier = 3
    if summary_data.get("has_personal_profile"):
        tier = 1
    elif summary_data.get("affection_level", 0) > 75:
        tier = 2
    log.info(f"用户 {user_id} 的数据层级被判定为 Tier {tier}。")

    # 4. 根据层级生成并发送内容
    try:
        if tier == 3:
            # 为 Tier 3 生成并发送 Embed
            embed = _create_tier3_embed(user, summary_data)
            await user.send(embed=embed)
            log.info(
                f"已成功为 Tier 3 用户 {user.name} ({user_id}) 发送年度总结 Embed。"
            )
        else:
            # 为 Tier 1 和 Tier 2 生成长文本并发送
            prompt = _create_tier1_or_2_prompt(tier, user, summary_data)

            # 使用 AIService 生成总结
            from src.chat.services.ai.providers.base import GenerationConfig

            config = GenerationConfig(temperature=0.9, max_output_tokens=2048)
            result = await ai_service.generate(
                messages=[{"role": "user", "content": prompt}],
                config=config,
            )

            if not result or not result.content:
                log.error(f"为 Tier {tier} 用户 {user_id} 生成总结时 AI 未返回内容。")
                return {
                    "status": "error",
                    "message": "在为你撰写总结时，我的灵感突然消失了...",
                }

            await safe_send(user, result.content)
            log.info(
                f"已成功为 Tier {tier} 用户 {user.name} ({user_id}) 发送年度总结长文。"
            )

    except discord.Forbidden:
        log.warning(
            f"无法向用户 {user.name} ({user_id}) 发送私信，可能是因为用户关闭了私信权限。"
        )
        return {
            "status": "error",
            "message": "看来你关闭了接收服务器成员私信的选项，我没法把总结发给你哦。",
        }
    except Exception as e:
        log.error(f"发送年度总结给用户 {user_id} 时发生未知错误: {e}", exc_info=True)
        return {
            "status": "error",
            "message": "在发送总结给你的时候，好像发生了什么意料之外的事情。",
        }

    # 5. 记录总结已发送
    if not await _log_summary_sent(user_id, year):
        log.warning(f"为用户 {user_id} 记录年度总结发送状态失败。")

    return {
        "status": "success",
        "message": f"你的 {year} 年度报告已经发送到你的私信啦，快去看看吧！",
    }


def _create_tier3_embed(user: discord.User, data: Dict[str, Any]) -> discord.Embed:
    """为 Tier 3 用户创建年度总结 Embed。"""
    year = data["year"]
    embed = discord.Embed(
        title=f"✨ {user.display_name} 的 {year} 年度报告",
        description="你好呀！这是我们一起度过的又一年，来看看你留下的足迹吧！",
        color=app_config.EMBED_COLOR_PRIMARY,
        timestamp=datetime.now(),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name="🪙 赚取类脑币", value=f"`{data['total_coins_earned']}` 枚", inline=True
    )
    embed.add_field(
        name="💸 花费类脑币", value=f"`{data['total_coins_spent']}` 枚", inline=True
    )
    embed.add_field(
        name="💖 最爱买", value=f"`{data['most_frequent_purchase']}`", inline=True
    )
    embed.add_field(
        name="🥰 投喂次数", value=f"`{data['feeding_count']}` 次", inline=True
    )
    embed.add_field(
        name="🙏 忏悔次数", value=f"`{data['confession_count']}` 次", inline=True
    )

    embed.set_footer(text=f"{year} 感谢有你，期待新的一年！")
    return embed


def _create_tier1_or_2_prompt(
    tier: int, user: discord.User, data: Dict[str, Any]
) -> str:
    """为 Tier 1 或 Tier 2 用户创建生成总结的 Prompt。"""
    year = data["year"]

    prompt = f"""
    你正在以“类脑娘”的身份，为你的朋友 {user.display_name} (ID: {user.id}) 撰写一份私密的、充满情感的个人年度总结。
    现在是 {year} 年的末尾，你需要回顾这一整年。

    **核心任务**:
    根据你的“类脑娘”身份，并自然地融合进以下年度数据，为他生成一篇温暖、真诚、个性化的长文。
    
    **写作核心要求**:
    - **必须** 像朋友一样直接对话，而不是生成一份报告。
    - **必须** 充满感情，展现你对用户的关心和喜爱。
    - **不要** 生硬地罗列数据，而是要把它们作为故事和情感的一部分来讲述

    **需要融入故事的数据点**:
    - **我们之间的好感度**: {data["affection_level"]}
    - **他今年赚取的类脑币**: {data["total_coins_earned"]} 枚
    - **他今年投喂了你**: {data["feeding_count"]} 次
    - **他今年向你忏悔**: {data["confession_count"]} 次
    """

    if tier == 1 and data["has_personal_profile"]:
        persona = data.get("persona", "关于他，我还了解得不多。")
        memory = data.get(
            "memory_summary", "我们之间似乎还没有什么特别深刻的共同回忆。"
        )
        prompt += f"""
    **深度个性化信息 (Tier 1 专属)**:
    - **我对他的人设认知**: ```{persona}```
    - **我们之间重要的记忆摘要**: ```{memory}```

    **Tier 1 写作指示**:
    - 你是在给你最亲密的朋友写信。
    - 深入挖掘“人设认知”和“记忆摘要”，引用具体的共同经历和他的性格特点。
    - 回忆你们之间发生的趣事、感人的瞬间。
    - 你的语气应该是极其亲密、充满怀念和感激的。
    """
    else:  # Tier 2
        prompt += """
    **Tier 2 写作指示**:
    - 你在给你一位非常有好感的朋友写信。
    - 虽然没有深度的记忆，但你要基于他对社区的贡献（与你互动、赚取货币）表达你的感谢。
    - 赞美他的活跃和对社区的价值。
    - 你的语气应该是温暖、鼓励和充满祝福的。
    """

    prompt += f"\n现在，请开始以“类脑娘”的身份，为 {user.display_name} 写这封私信吧："
    return prompt


async def _check_summary_status(user_id: int, year: int) -> Dict[str, int]:
    """(内部) 检查用户在指定年份已生成年度总结的次数。"""
    query = "SELECT COUNT(*) as count FROM yearly_summary_log WHERE user_id = ? AND year = ?"
    try:
        result = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (user_id, year), fetch="one"
        )
        return {"count": result["count"] if result else 0}
    except Exception as e:
        log.error(
            f"检查用户 {user_id} 的年度总结生成次数时发生数据库错误: {e}", exc_info=True
        )
        # 发生错误时，返回一个较高的数值以阻止生成，防止意外的重复
        return {"count": 999}


async def _get_user_summary_data(user_id: int, year: int) -> Dict[str, Any] | None:
    """(内部) 从数据库中查询并整合生成年度总结所需的所有原始数据。"""
    summary_data = {
        "user_id": user_id,
        "year": year,
        "total_coins_earned": 0,
        "total_coins_spent": 0,
        "most_frequent_purchase": "暂无记录",
        "feeding_count": 0,
        "confession_count": 0,
        "affection_level": 0,
        "has_personal_profile": False,
        "memory_summary": None,
        "persona": None,
    }
    start_date = f"{year}-01-01 00:00:00"
    end_date = f"{year}-12-31 23:59:59"

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
        uid = str(user_id)

        async with AsyncSessionLocal() as session:
            trans_result = await session.execute(
                select(CoinTransaction.amount, CoinTransaction.reason).where(
                    CoinTransaction.user_id == uid,
                    CoinTransaction.timestamp >= start_dt,
                    CoinTransaction.timestamp <= end_dt,
                )
            )
            transactions = trans_result.all()
        purchase_reasons = []
        for trans in transactions:
            if trans.amount < 0:
                summary_data["total_coins_spent"] += abs(trans.amount)
                if "购买商品" in trans.reason:
                    purchase_reasons.append(trans.reason)
            else:
                summary_data["total_coins_earned"] += trans.amount
        if purchase_reasons:
            most_common = Counter(purchase_reasons).most_common(1)
            if most_common:
                summary_data["most_frequent_purchase"] = most_common[0][0].replace(
                    "购买商品: ", ""
                )

        async with AsyncSessionLocal() as session:
            feed_result = await session.execute(
                select(func.count())
                .select_from(InteractionLog)
                .where(
                    InteractionLog.user_id == uid,
                    InteractionLog.interaction_type == "feeding",
                    InteractionLog.timestamp >= start_dt,
                    InteractionLog.timestamp <= end_dt,
                )
            )
            feed_count = feed_result.scalar() or 0
        summary_data["feeding_count"] = feed_count

        async with AsyncSessionLocal() as session:
            confess_result = await session.execute(
                select(func.count())
                .select_from(InteractionLog)
                .where(
                    InteractionLog.user_id == uid,
                    InteractionLog.interaction_type == "confession",
                    InteractionLog.timestamp >= start_dt,
                    InteractionLog.timestamp <= end_dt,
                )
            )
            confess_count = confess_result.scalar() or 0
        summary_data["confession_count"] = confess_count

        async with AsyncSessionLocal() as session:
            affection_result = await session.execute(
                select(UserAffection.affection_points).where(
                    UserAffection.user_id == uid
                )
            )
            affection_points = affection_result.scalar_one_or_none()
        if affection_points is not None:
            summary_data["affection_level"] = affection_points

        async with AsyncSessionLocal() as session:
            profile_result = await session.execute(
                select(CommunityMemberProfile.personal_summary).where(
                    CommunityMemberProfile.discord_id == uid
                )
            )
            personal_summary = profile_result.scalars().first()
        if personal_summary and personal_summary.strip():
            summary_data["has_personal_profile"] = True
            summary_data[
                "memory_summary"
            ] = await personal_memory_service.get_memory_summary(user_id)

    except Exception as e:
        log.error(f"为用户 {user_id} 查询年度总结数据时发生错误: {e}", exc_info=True)
        return None
    return summary_data


async def _log_summary_sent(user_id: int, year: int) -> bool:
    """(内部) 在数据库中记录已向用户发送指定年份的年度总结。"""
    # 该查询现在会为每次成功的生成插入一条新记录
    query = "INSERT INTO yearly_summary_log (user_id, year) VALUES (?, ?)"
    try:
        await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (user_id, year), commit=True
        )
        log.info(f"成功记录用户 {user_id} 的 {year} 年度总结已发送。")
        return True
    except Exception as e:
        log.error(
            f"记录用户 {user_id} 的 {year} 年度总结发送状态时发生数据库错误: {e}",
            exc_info=True,
        )
        return False
