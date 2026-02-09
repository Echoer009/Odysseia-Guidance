import discord
import logging
from typing import Dict, Any, List
import httpx
import base64

# 假设 coin_service 的路径是正确的
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


@tool_metadata(
    name="查询资料",
    description="查询用户的类脑币余额、头像、角色等信息",
    emoji="👤",
    category="用户信息",
)
async def get_user_profile(
    user_id: str,
    queries: List[str],
    log_detailed: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """
    查询用户的个人资料，可选择性地包括多个字段。
    [调用指南]
    - **自主决策**: 只要认为有必要就可以调用
    - **按需查询**: 根据上下文，在 `queries` 列表中指定一个或多个需要查询的字段，以获取必要的信息。
    - **查询当前对话用户**: 如果你要查询当然对话用户信息,系统会自动提供用户的数字ID，无需填写 `user_id`,调用工具即可。

    Args:
        user_id (str): 目标用户的 Discord 数字ID。**注意**: 如果是查询当前对话用户, 此参数将由系统自动填充, 模型无需处理。
        queries (List[str]): 需要查询的字段列表。有效值: "balance", "avatar", "roles"。

    Returns:
        一个包含查询结果和状态的字典。
    """
    # 从 kwargs 安全地获取由系统注入的 bot 和 guild 实例
    bot = kwargs.get("bot")
    guild = kwargs.get("guild")

    if not bot:
        return {"error": "Bot instance is not available."}

    if log_detailed:
        log.info(
            f"--- [工具执行]: get_user_profile, user_id={user_id}, queries={queries} ---"
        )

    if not user_id or not user_id.isdigit():
        return {"error": f"Invalid or missing user_id provided: {user_id}"}

    target_id = int(user_id)
    # 使用集合处理 queries 以提高效率并自动去重
    query_set = set(queries)

    result = {
        "user_id": str(target_id),
        "queries_requested": queries,
        "queries_successful": [],
        "profile": {},
        "errors": [],
    }

    # --- 查询分支 ---

    # 1. 查询头像 (Avatar)
    if "avatar" in query_set:
        try:
            user = await bot.fetch_user(target_id)
            if user and user.display_avatar:
                avatar_url = str(user.display_avatar.url)
                result["profile"]["avatar_url"] = avatar_url

                async with httpx.AsyncClient() as client:
                    response = await client.get(avatar_url)
                    response.raise_for_status()
                    image_bytes = response.content
                    result["profile"]["avatar_image_base64"] = base64.b64encode(
                        image_bytes
                    ).decode("utf-8")

                result["queries_successful"].append("avatar")
                log.info(f"成功获取用户 {target_id} 的头像 URL 并下载了图片。")
            else:
                result["errors"].append("User has no avatar.")
        except discord.NotFound:
            result["errors"].append("User not found on Discord for avatar query.")
        except httpx.HTTPStatusError as e:
            error_msg = f"下载头像时发生HTTP错误: {e}"
            result["errors"].append(error_msg)
            log.error(error_msg, exc_info=True)
        except Exception as e:
            error_msg = f"获取头像时发生未知错误: {str(e)}"
            result["errors"].append(error_msg)
            log.error(error_msg, exc_info=True)

    # 2. 查询角色 (Roles)
    if "roles" in query_set:
        if not guild:
            result["errors"].append(
                "Guild information is not available for roles query."
            )
        else:
            try:
                member = guild.get_member(target_id)
                if member:
                    # 过滤掉 @everyone 角色，并获取角色名称
                    role_names = [
                        role.name for role in member.roles if role.name != "@everyone"
                    ]
                    result["profile"]["roles"] = role_names
                    result["queries_successful"].append("roles")
                    log.info(f"成功获取用户 {target_id} 在服务器 {guild.name} 的角色。")
                else:
                    result["errors"].append("User is not a member of this server.")
            except Exception as e:
                error_msg = f"获取角色时发生未知错误: {str(e)}"
                result["errors"].append(error_msg)
                log.error(error_msg, exc_info=True)

    # 3. 查询余额 (Balance)
    if "balance" in query_set:
        try:
            balance = await coin_service.get_balance(target_id)
            result["profile"]["balance"] = {"amount": balance, "name": "类脑币"}
            result["queries_successful"].append("balance")
            log.info(f"成功获取用户 {target_id} 的余额: {balance}")
        except Exception as e:
            error_msg = f"获取余额时发生未知错误: {str(e)}"
            result["errors"].append(error_msg)
            log.error(error_msg, exc_info=True)

    log.info(
        f"用户 {target_id} 的个人资料查询完成。成功: {result['queries_successful']}, 失败: {len(result['errors'])} 项。"
    )
    return result
