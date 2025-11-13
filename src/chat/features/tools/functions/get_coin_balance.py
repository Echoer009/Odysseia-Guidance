import logging
from typing import Dict, Any, Optional

from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)


async def get_coin_balance(user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    获取指定用户的类脑币余额。此工具用于以下两种场景：
    1. 当用户想查询自己的余额时,在这种情况下，请不要在调用时传入 user_id，系统会自动传入当前用户ID。
    2. 当用户想查询其他特定用户的余额时：例如“看看 <@123456789012345678> 有多少钱”。在这种情况下，请传入目标用户的纯数字ID。

    Args:
        user_id (Optional[str]): 目标用户的纯数字 Discord ID (例如: "123456789012345678")。如果用户想查询自己的余额，则应省略此参数。

    Returns:
        一个包含用户余额的字典，如果失败则返回错误信息。
    """
    log.info(f"--- [工具执行]: get_coin_balance, 参数: user_id={user_id} ---")

    if not user_id or not user_id.isdigit():
        log.warning(f"提供了无效的 user_id: {user_id}。")
        return {"error": f"Invalid or missing user_id provided: {user_id}"}

    try:
        target_id = int(user_id)
        balance = await coin_service.get_balance(target_id)
        log.info(f"成功获取用户 {target_id} 的余额: {balance}")
        return {"user_id": str(target_id), "balance": balance}

    except Exception as e:
        log.error(f"获取用户 {user_id} 余额时发生未知错误。", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}
