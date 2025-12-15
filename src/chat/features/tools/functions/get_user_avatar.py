import discord
import aiohttp
import logging
from typing import Dict, Any, Optional
from PIL import Image
import io

# 获取日志记录器
log = logging.getLogger(__name__)


async def get_user_avatar(
    user_id: str, log_detailed: bool = False, **kwargs
) -> Dict[str, Any]:
    """
    获取用户的 Discord 头像。
    [调用指南]
    - 当用户想看自己的头像时，请不要传递 `user_id` 参数，系统会自动获取。
    - 当用户想看其他人的头像时 (例如通过 @mention)，请传递 `user_id`。
    - "看看我的头像" -> 调用 get_user_avatar()
    - "看看<@123456789>的头像" -> 调用 get_user_avatar(user_id="123456789")

    Args:
        user_id (str): 目标用户的 Discord 数字ID。如果模型未提供，系统会自动填充为消息发送者的ID。

    Returns:
        一个包含图片二进制数据的字典
    """
    bot = kwargs.get("bot")
    if log_detailed:
        log.info(
            f"--- [工具执行]: get_user_avatar (新版-图片下载), 参数: user_id={user_id} ---"
        )

    if not bot:
        log.error("工具 'get_user_avatar' 执行失败: Discord bot 实例不可用。")
        return {"error": "Discord bot instance is not available."}

    # ToolService 保证了 user_id 在执行时总是有效的
    if not user_id.isdigit():
        log.warning(f"接收到无效的 user_id: {user_id}。")
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

                    # 如果是 GIF，则转换为 PNG 以兼容 Gemini API
                    if mime_type == "image/gif":
                        if log_detailed:
                            log.info("检测到 GIF 头像，正在转换为 PNG...")
                        try:
                            with Image.open(io.BytesIO(image_bytes)) as img:
                                # 提取第一帧并保存为 PNG
                                output_buffer = io.BytesIO()
                                img.save(output_buffer, format="PNG")
                                image_bytes = output_buffer.getvalue()
                                mime_type = "image/png"  # 更新 MIME 类型
                                if log_detailed:
                                    log.info(
                                        f"成功转换为 PNG，新大小: {len(image_bytes)} bytes"
                                    )
                        except Exception as e:
                            log.error(f"GIF 转换为 PNG 失败: {e}", exc_info=True)
                            # 转换失败，返回错误而不是原始 GIF
                            return {"error": "Failed to convert animated avatar."}

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
