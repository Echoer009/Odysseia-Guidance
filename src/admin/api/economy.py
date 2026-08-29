import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])

SHOP_ANNOUNCEMENT_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "chat"
    / "features"
    / "odysseia_coin"
    / "shop_announcement.md"
)


class CoinsAdjust(BaseModel):
    user_id: int
    amount: int
    reason: str


class AnnouncementUpdate(BaseModel):
    content: str


@router.post("/api/economy/adjust")
async def adjust_coins(body: CoinsAdjust, user_id: int = Depends(require_admin)):
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="调整原因不能为空")
    if body.amount == 0:
        raise HTTPException(status_code=400, detail="调整金额不能为零")
    if body.amount > 0:
        new_balance = await coin_service.add_coins(body.user_id, body.amount, reason)
    else:
        new_balance = await coin_service.remove_coins(
            body.user_id, -body.amount, reason
        )
        if new_balance is None:
            current = await coin_service.get_balance(body.user_id)
            raise HTTPException(
                status_code=400,
                detail=f"用户余额不足，无法扣除（当前余额 {current}）",
            )
    await audit_log_service.log(
        user_id,
        "adjust_coins",
        "user_coins",
        str(body.user_id),
        {"amount": body.amount, "reason": reason, "new_balance": new_balance},
    )
    return {"success": True, "new_balance": new_balance}


@router.get("/api/shop/announcement")
async def get_shop_announcement():
    if not SHOP_ANNOUNCEMENT_PATH.is_file():
        return {"content": ""}
    return {"content": SHOP_ANNOUNCEMENT_PATH.read_text(encoding="utf-8")}


@router.put("/api/shop/announcement")
async def update_shop_announcement(
    body: AnnouncementUpdate, user_id: int = Depends(require_admin)
):
    SHOP_ANNOUNCEMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SHOP_ANNOUNCEMENT_PATH.write_text(body.content, encoding="utf-8")
    await audit_log_service.log(
        user_id,
        "update",
        "shop_announcement",
        "shop_announcement.md",
        {"length": len(body.content)},
    )
    return {"success": True}
