import discord
import aiohttp
import logging
from typing import Dict, Any

# 获取日志记录器
log = logging.getLogger(__name__)


async def get_user_avatar(
    user_id: str, log_detailed: bool = False, **kwargs
) -> Dict[str, Any]:
    """
    获取指定 Discord 用户 ID 的头像图片数据。
    重要: 如果用户使用 "我"、"我的" 等词语指代自己，请不要提供 user_id 参数，系统会自动使用提问者的 ID。
    只有当用户明确提到其他人的 ID 时，才提供 user_id 参数。

    Args:
        user_id: (可选) 用户的 Discord ID。仅在用户明确指定时使用。

    Returns:
        一个包含图片 MIME 类型和二进制数据的字典，如果失败则返回错误信息。
    """
    bot = kwargs.get("bot")
    if log_detailed:
        log.info(
            f"--- [工具执行]: get_user_avatar (新版-图片下载), 参数: user_id={user_id} ---"
        )

    if not bot:
        log.error("工具 'get_user_avatar' 执行失败: Discord bot 实例不可用。")
        return {"error": "Discord bot instance is not available."}

    if not user_id or not user_id.isdigit():
        log.warning(f"提供了无效的 user_id: {user_id}。")
        return {"error": f"Invalid user_id provided: {user_id}"}

    try:
        target_id = int(user_id)
        if log_detailed:
            log.info(f"正在获取用户 {target_id} 的信息...")
        user = await bot.fetch_user(target_id)
        if not user or not user.display_avatar:
            log.warning(f"未找到用户 {target_id} 或该用户没有头像。")
            return {"error": "User not found or user has no avatar."}

        avatar_url = str(user.display_avatar.url)
        if log_detailed:
            log.info(f"成功获取头像 URL: {avatar_url}，准备下载...")

        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as response:
                if response.status == 200:
                    image_bytes = await response.read()
                    mime_type = response.headers.get("Content-Type", "image/png")
                    if log_detailed:
                        log.info(
                            f"成功下载头像，大小: {len(image_bytes)} bytes, MIME: {mime_type}"
                        )
                    # 返回一个特殊结构，包含图片数据，供上游服务处理
                    return {"image_data": {"mime_type": mime_type, "data": image_bytes}}
                else:
                    log.error(f"下载头像失败，HTTP 状态码: {response.status}")
                    return {
                        "error": f"Failed to download avatar, status: {response.status}"
                    }

    except discord.NotFound:
        log.warning(f"在 Discord 中未找到 ID 为 {user_id} 的用户。")
        return {"error": f"User with ID {user_id} not found in Discord."}
    except Exception as e:
        log.error(f"获取用户 {user_id} 头像时发生未知错误。", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}
