import logging
from typing import Dict, Any, Optional

from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)


async def get_coin_balance(user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    查询用户“类脑币”余额
    [调用指南]
    - 仅在用户明确想查询金币余额时使用。
    - 必须从用户的发言中（如 @mention）获取 `user_id`。
    - "查查<@12345>有多少钱" -> `user_id="12345"`

    Args:
        user_id (Optional[str]): 目标用户的 Discord ID。查自己时省略。

    Returns:
        一个包含用户余额的字典。
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
