# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

import discord
from src.chat.utils.database import chat_db_manager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

client = discord.Client(intents=discord.Intents.none())

GUILD_ID = int(os.getenv("GUILD_ID", "0").split(",")[0].strip() or "0")
GUIDANCE_CHANNEL_ID = int(os.getenv("GUIDANCE_CHANNEL_ID") or "0")


def _section(title: str) -> None:
    print(f"\n[{title}]")


async def diagnose():
    print("=" * 60)
    print("引导频道消息缓存诊断")
    print("=" * 60)

    _section("1. 环境变量")
    print(f"  GUILD_ID             = {GUILD_ID}")
    print(f"  GUIDANCE_CHANNEL_ID  = {GUIDANCE_CHANNEL_ID}")
    if GUILD_ID == 0 or GUIDANCE_CHANNEL_ID == 0:
        print("  ❌ GUILD_ID 或 GUIDANCE_CHANNEL_ID 未配置,终止。")
        return

    _section("2. 数据库缓存 (global_settings)")
    msg_id_raw = await chat_db_manager.get_global_setting("guidance_message_id")
    url_cached = await chat_db_manager.get_global_setting("guidance_url")
    print(f"  guidance_message_id  = {msg_id_raw}")
    print(f"  guidance_url         = {url_cached}")
    if not msg_id_raw:
        print("  ❌ 数据库里没有 guidance_message_id(_ensure_channel_message 还没跑过或失败)。")
        return

    try:
        msg_id = int(msg_id_raw)
    except (TypeError, ValueError):
        print(f"  ❌ guidance_message_id 不是合法整数: {msg_id_raw!r}")
        return

    _section(f"3. 获取频道 {GUIDANCE_CHANNEL_ID}")
    try:
        channel = await client.fetch_channel(GUIDANCE_CHANNEL_ID)
    except discord.NotFound:
        print("  ❌ 频道不存在(bot 看不到该频道,ID 错误或 bot 不在服务器)。")
        return
    except discord.Forbidden:
        print("  ❌ bot 没有查看该频道的权限。")
        return
    print(
        f"  ✅ 频道存在: #{getattr(channel, 'name', '?')} "
        f"(类型: {type(channel).__name__})"
    )
    if not isinstance(
        channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)
    ):
        print(
            f"  ❌ 频道类型 {type(channel).__name__} 不支持消息,"
            f"guidance_cog 只支持 TextChannel/VoiceChannel/Thread。"
        )
        return

    _section(f"4. 获取消息 {msg_id} (在频道 {GUIDANCE_CHANNEL_ID} 内)")
    try:
        msg = await channel.fetch_message(msg_id)
    except discord.NotFound:
        print(f"  ❌ 该消息不在频道 {GUIDANCE_CHANNEL_ID} 内!")
        print(
            f"     这就是缓存陈旧/跨频道问题:\n"
            f"     _get_guidance_jump_url 会拼出\n"
            f"     https://discord.com/channels/{GUILD_ID}/{GUIDANCE_CHANNEL_ID}/{msg_id}\n"
            f"     但这条消息不在这个频道里 → 用户点链接看到无权限或消息不存在。"
        )
        return
    except discord.Forbidden:
        print("  ❌ bot 没有读取频道历史消息的权限。")
        return
    print("  ✅ 消息存在")

    _section("5. 详细校验")
    bot_id = client.user.id if client.user else None
    is_bot_msg = bot_id is not None and msg.author.id == bot_id
    same_channel = msg.channel.id == GUIDANCE_CHANNEL_ID
    has_components = bool(msg.components)
    print(f"  消息 author             = {msg.author} (id={msg.author.id})")
    print(f"  bot user id             = {bot_id}")
    print(f"  是 bot 自己发的?        = {'✅' if is_bot_msg else '❌ 不是'}")
    print(
        f"  实际所在频道            = #{getattr(msg.channel, 'name', '?')} "
        f"(id={msg.channel.id})"
    )
    print(f"  与 GUIDANCE_CHANNEL_ID 一致? = {'✅' if same_channel else '❌ 不一致'}")
    print(f"  消息创建时间            = {msg.created_at}")
    print(
        f"  有按钮组件?             = "
        f"{'✅' if has_components else '⚠️ 没有(可能被剥了)'}"
    )

    _section("6. URL 对比")
    expected = f"https://discord.com/channels/{GUILD_ID}/{GUIDANCE_CHANNEL_ID}/{msg_id}"
    real = str(msg.jump_url)
    print(f"  _get_guidance_jump_url 返回 = {expected}")
    print(f"  消息真实 jump_url            = {real}")
    print(
        f"  两者一致? = "
        f"{'✅' if expected == real else '❌ 不一致(说明 GUILD_ID 或 CHANNEL_ID 配错)'}"
    )

    _section("结论")
    if is_bot_msg and same_channel and has_components and expected == real:
        print("  ✅ 缓存 message_id 健康,jump URL 配置正确。")
        print("     第3点(缓存陈旧/跨频道)排除。无权限问题不在这里。")
    else:
        print("  ⚠️ 发现问题,见上方标记。")


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ 未在 .env 找到 DISCORD_TOKEN")
        return

    await chat_db_manager.init_async()
    try:
        await client.login(token)
        log.info("已登录 Discord (REST 模式,不连 gateway)")
        await diagnose()
    except discord.LoginFailure:
        print("❌ Discord 登录失败,检查 DISCORD_TOKEN。")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
