import logging
from typing import Dict, Any, Optional

from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)


async def get_coin_balance(user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    查询用户所拥有的“类脑币”余额。
    - 当用户查询自己的余额时，无需传入 `user_id`。
    - 当用户查询他人的余额时，则需要传入目标的 `user_id`。
    - 你无法查询自己的余额

    Args:
        user_id (Optional[str]): 目标用户的 Discord ID，可以是纯数字格式，也可以是 Discord 的 @ 提及格式 (例如: "<@123456789012345678>")。如果用户想查询自己的余额，则应省略此参数。

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
