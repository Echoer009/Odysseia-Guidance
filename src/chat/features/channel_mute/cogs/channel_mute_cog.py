# -*- coding: utf-8 -*-

import discord
import datetime
from discord.ext import commands
from discord import app_commands
import logging

from src.chat.utils.database import chat_db_manager
from src.chat.config.chat_config import CHANNEL_MUTE_CONFIG
from src.chat.config import chat_config

log = logging.getLogger(__name__)


class ChannelMuteCog(commands.Cog):
    """
    处理与频道禁言相关的命令和事件。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vote_messages = {}  # message_id: {"channel_id": int, "created_at": datetime}

    @app_commands.command(name="闭嘴", description="发起投票，让类脑娘在此频道禁言。")
    async def mute(self, interaction: discord.Interaction):
        """
        发起一个投票，如果票数足够，机器人将在当前频道被禁言。
        """
        channel_id = interaction.channel_id

        # 0. 检查是否在豁免频道
        # 检查是否在豁免频道，或当前频道是否为帖子
        is_unrestricted = (
            channel_id in chat_config.UNRESTRICTED_CHANNEL_IDS
            or isinstance(interaction.channel, discord.Thread)
        )
        if is_unrestricted:
            await interaction.response.send_message(
                "在这个频道里，我可是有豁免权的哦，不能让我闭嘴！", ephemeral=True
            )
            return

        # 1. 检查频道是否已经被禁言
        if await chat_db_manager.is_channel_muted(channel_id):
            await interaction.response.send_message(
                "我已经在这个频道闭嘴了哦。", ephemeral=True
            )
            return

        # 2. 创建并发送投票 embed
        threshold = CHANNEL_MUTE_CONFIG["VOTE_THRESHOLD"]
        mute_duration = CHANNEL_MUTE_CONFIG["MUTE_DURATION_MINUTES"]
        description = (
            f"{interaction.user.mention} 发起了投票…\n\n"
            f"如果大家投了 {threshold} 票 ✅，我就会在这个频道里“下线” {mute_duration} 分钟，不再回应任何消息和指令啦。\n\n"
            "不过放心，这不会影响到子区（线程）里的悄悄话哦！"
        )
        embed = discord.Embed(
            title="呜…要让我在这里闭嘴吗？",
            description=description,
            color=discord.Color.orange(),
        )
        duration = CHANNEL_MUTE_CONFIG["VOTE_DURATION_MINUTES"]
        embed.set_footer(text=f"哼，你们只有{duration}分钟时间来决定！")

        await interaction.response.send_message(embed=embed)
        vote_message = await interaction.original_response()

        # 3. 存储消息ID和创建时间以供追踪
        self.vote_messages[vote_message.id] = {
            "channel_id": channel_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
        }
        log.info(f"在频道 {channel_id} 发起了禁言投票，消息ID: {vote_message.id}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        监听反应事件，用于处理禁言投票。
        """
        # 1. 检查是否是我们关心的投票消息
        vote_info = self.vote_messages.get(payload.message_id)
        if not vote_info:
            return

        # 2. 检查投票是否过期
        duration = CHANNEL_MUTE_CONFIG["VOTE_DURATION_MINUTES"]
        expires_at = vote_info["created_at"] + datetime.timedelta(minutes=duration)
        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            log.info(f"投票 {payload.message_id} 已过期。")
            del self.vote_messages[payload.message_id]
            return

        # 3. 忽略机器人自己的反应
        if payload.user_id == self.bot.user.id:
            return

        # 4. 检查是否是 ✅ 反应
        if str(payload.emoji) != "✅":
            return

        channel_id = vote_info["channel_id"]
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
            for reaction in message.reactions:
                if str(reaction.emoji) == "✅":
                    # 5. 检查票数是否达到阈值
                    threshold = CHANNEL_MUTE_CONFIG["VOTE_THRESHOLD"]
                    if reaction.count >= threshold:
                        # 尝试以原子方式移除投票消息。如果消息已被移除，
                        # 这意味着另一个并发事件已经处理了它。
                        vote_info_popped = self.vote_messages.pop(
                            payload.message_id, None
                        )

                        if vote_info_popped:
                            # 如果我们成功地弹出了消息，那么就由我们来执行禁言操作。
                            mute_duration = CHANNEL_MUTE_CONFIG["MUTE_DURATION_MINUTES"]
                            await chat_db_manager.add_muted_channel(
                                channel_id, mute_duration
                            )
                            await channel.send(
                                f"呜…好吧，那人家就在这里不说话了，{mute_duration} 分钟后再理你们。"
                            )
                            log.info(
                                f"频道 {channel_id} 已被投票禁言 {mute_duration} 分钟。"
                            )

                        # 无论我们是否执行了禁言，投票都已经结束。
                        break
        except discord.NotFound:
            log.warning(f"无法找到投票消息 {payload.message_id}，可能已被删除。")
            del self.vote_messages[payload.message_id]
        except Exception as e:
            log.error(f"处理投票反应时出错: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelMuteCog(bot))
