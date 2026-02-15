# -*- coding: utf-8 -*-

"""
春节红包工具（简化版）
"""

import random
import logging
from typing import Dict, Any
from datetime import datetime

import discord
from discord import ui

from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.utils.database import chat_db_manager
from src.chat.utils.prompt_utils import replace_emojis


log = logging.getLogger(__name__)


class RedEnvelopeView(ui.View):
    """红包领取视图"""

    def __init__(self, user_id: int, blessing_text: str):
        super().__init__(timeout=None)  # 永久有效，直到用户点击
        self.user_id = user_id
        self.blessing_text = blessing_text
        self.claimed = False

    @ui.button(
        label="🧧 开启红包",
        style=discord.ButtonStyle.success,
        custom_id="red_envelope_claim",
    )
    async def claim_button(self, interaction: discord.Interaction, button: ui.Button):
        """用户点击领取红包"""
        try:
            # 验证用户
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "这不是你的红包哦～", ephemeral=True
                )
                return

            # 检查是否已领取
            if self.claimed:
                await interaction.response.send_message(
                    "你已经领取过这个红包了！", ephemeral=True
                )
                return

            # 检查今日是否已领取过（每日限制）
            user_id_int = int(self.user_id)
            last_date = await chat_db_manager.get_last_red_envelope_date(user_id_int)
            today = datetime.now().strftime("%Y-%m-%d")
            if last_date == today:
                await interaction.response.send_message(
                    "你今天已经领取过红包了，明天再来吧！", ephemeral=True
                )
                return

            # 随机金额
            amount = random.randint(500, 1000)

            # 发放金币
            await coin_service.add_coins(
                user_id=user_id_int, amount=amount, reason="春节红包奖励"
            )

            # 更新领取日期
            await chat_db_manager.set_last_red_envelope_date(user_id_int, today)

            # 标记为已领取
            self.claimed = True
            button.disabled = True
            button.label = "✅ 已领取"

            # 更新embed
            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                embed.title = "🧧 红包已开启！"
                embed.color = discord.Color.gold()
                embed.description = f"**恭喜！**\n\n你收到了 **{amount} 类脑币**！\n\n> {self.blessing_text}"
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.send_message(
                    f"**恭喜！**\n\n你收到了 **{amount} 类脑币**！\n\n> {self.blessing_text}",
                    ephemeral=True,
                )
            log.info(f"用户 {user_id_int} 领取红包成功，获得 {amount} 类脑币")

        except Exception as e:
            log.error(f"处理红包领取时出错: {e}", exc_info=True)
            await interaction.response.send_message(
                "领取红包时发生错误，请联系管理员。", ephemeral=True
            )


@tool_metadata(
    name="发送红包",
    description="类脑娘发红包啦",
    emoji="🧧",
    category="春节活动",
)
async def spring_festival_red_envelope(
    blessing_text: str,
    **kwargs,
) -> Dict[str, Any]:
    """
    发送春节红包给当前用户。调用此工具时，必须传入blessing_text。
    工具会向当前用户私信发送一个红包，用户点击"开启红包"按钮后随机获得500-1000类脑币和祝福。

    [调用指南]
    - **触发条件**: 用户发送"新年快乐"、"除夕快乐"、"新春快乐"等春节祝福语
    - **每日限制**: 每个用户每天只能领取一次红包（由系统自动检查）
    - **参数说明**:
      - blessing_text: 生成的祝福语内容（必填，需要个性化）

    Args:
        blessing_text (str): AI生成的祝福语内容

    Returns:
        一个包含操作结果和状态的字典。
    """
    # 从kwargs获取当前用户ID
    user_id = kwargs.get("user_id")
    if not user_id:
        result = {
            "success": False,
            "message": "无法获取当前用户ID",
            "amount": 0,
            "is_daily_limit": False,
        }
        return result

    result = {
        "user_id": user_id,
        "success": False,
        "message": "",
        "amount": 0,
        "is_daily_limit": False,
    }

    try:
        target_id = int(user_id)
    except ValueError:
        result["message"] = f"无效的用户ID: {user_id}"
        return result

    # 检查今日是否已领取（提前检查，避免发送DM后无法领取）
    try:
        last_date = await chat_db_manager.get_last_red_envelope_date(target_id)
        today = datetime.now().strftime("%Y-%m-%d")
        if last_date == today:
            result["is_daily_limit"] = True
            result["message"] = "用户今日已领取过红包，请明天再来吧！"
            log.info(f"用户 {target_id} 今日已领取过红包，跳过发送")
            return result
    except Exception as e:
        log.error(f"查询用户 {target_id} 红包记录时出错: {e}", exc_info=True)
        # 出错时继续执行，不阻止发送

    # 替换表情符号
    processed_blessing = replace_emojis(blessing_text)

    # 创建embed（不显示具体祝福语，保持神秘感）
    embed = discord.Embed(
        title="🧧 春节红包",
        description="你收到了一份来自类脑娘的新年祝福！",
        color=discord.Color.gold(),
    )
    embed.set_footer(text="每人每天限领一次哦～")

    # 创建视图
    view = RedEnvelopeView(user_id=target_id, blessing_text=processed_blessing)

    # 发送DM
    try:
        # 从kwargs获取bot和guild实例
        bot = kwargs.get("bot")
        guild = kwargs.get("guild")
        if not bot:
            result["message"] = "Bot实例不可用，无法发送DM"
            return result

        # 从guild获取用户对象（用户正在交互，一定在guild中）
        if guild:
            user = guild.get_member(target_id)
            if not user:
                result["message"] = f"无法在服务器中找到用户 {target_id}"
                return result
        else:
            # fallback: 尝试从bot缓存或API获取
            user = bot.get_user(target_id)
            if not user:
                result["message"] = f"无法找到用户 {target_id}"
                return result

        await user.send(embed=embed, view=view)
        result["success"] = True
        result["message"] = "红包DM已发送成功"
        log.info(f"已向用户 {target_id} 发送红包DM")

    except discord.Forbidden:
        result["message"] = "无法向该用户发送DM（用户可能关闭了私信权限）"
        log.warning(f"无法向用户 {target_id} 发送DM")
    except Exception as e:
        log.error(f"发送红包DM时出错: {e}", exc_info=True)
        result["message"] = f"发送DM时发生错误: {str(e)}"

    return result
