import os
import requests
import logging
import asyncio
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

# --- 类脑币服务 ---
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.games.config import blackjack_config
from src.chat.features.games.services.blackjack_service import blackjack_service

# 从根目录加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI()
log = logging.getLogger(__name__)

# --- 用户操作锁，防止竞态条件 ---
user_locks = defaultdict(asyncio.Lock)


# --- 应用生命周期事件 ---
@app.on_event("startup")
async def startup_event():
    """在应用启动时初始化数据库表"""
    log.info("Application startup: Initializing services...")
    await blackjack_service.initialize()
    log.info("Blackjack service initialized.")


# --- 中间件：添加详细的请求日志 ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    log.info(f"收到请求: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        log.info(
            f"请求完成: {request.method} {request.url.path} - 状态码: {response.status_code}"
        )
        return response
    except Exception as e:
        log.error(
            f"请求处理出错: {request.method} {request.url.path} - 错误: {e}",
            exc_info=True,
        )
        # 重新抛出异常，以便FastAPI的默认异常处理可以捕获它
        raise


# --- 安全性和依赖 ---
auth_scheme = HTTPBearer()


async def get_current_user_id(
    token: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> int:
    """
    依赖项：从Bearer Token中获取用户信息并返回用户ID。
    """
    headers = {"Authorization": f"Bearer {token.credentials}"}
    log.info("正在从Discord API获取用户信息...")
    try:
        response = requests.get("https://discord.com/api/users/@me", headers=headers)
        response.raise_for_status()
        user_data = response.json()
        user_id = int(user_data["id"])
        log.info(f"成功识别用户: {user_data['username']} ({user_id})")
        return user_id
    except requests.exceptions.RequestException as e:
        log.error("从Discord API获取用户信息失败。", exc_info=True)
        if e.response is not None:
            log.error(f"Discord API响应状态: {e.response.status_code}")
            log.error(f"Discord API响应内容: {e.response.text}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class TokenRequest(BaseModel):
    code: str


class BetRequest(BaseModel):
    amount: int


class PayoutRequest(BaseModel):
    result: str  # 'win', 'blackjack', 'push'


@app.post("/api/token")
async def exchange_code_for_token(request: TokenRequest):
    """API: 用Discord返回的code换取access_token"""
    log.info(f"收到令牌交换请求，代码: '{request.code[:10]}...'")
    client_id = os.getenv("VITE_DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")

    if not client_id or not client_secret:
        log.error("服务器缺少 VITE_DISCORD_CLIENT_ID 或 DISCORD_CLIENT_SECRET")
        raise HTTPException(
            status_code=500, detail="Server is missing Discord credentials"
        )

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": request.code,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    log.info("正在向Discord API发送令牌交换请求...")
    try:
        response = requests.post(
            "https://discord.com/api/oauth2/token", data=data, headers=headers
        )
        response.raise_for_status()
        log.info("成功交换代码获取令牌。")
        return JSONResponse(content=response.json())
    except requests.exceptions.RequestException as e:
        log.error("与Discord API交换代码失败。", exc_info=True)
        if e.response is not None:
            log.error(f"Discord API响应状态: {e.response.status_code}")
            log.error(f"Discord API响应内容: {e.response.text}")
        raise HTTPException(
            status_code=500, detail="Failed to exchange code with Discord"
        )


@app.get("/api/user")
async def get_user_info(user_id: int = Depends(get_current_user_id)):
    """
    API: 获取当前用户信息，包括类脑币余额。
    """
    log.info(f"正在获取用户 {user_id} 的余额")
    try:
        balance = await coin_service.get_balance(user_id)
        log.info(f"用户 {user_id} 的余额为 {balance}")

        # --- 从配置文件获取荷官阈值 ---
        dealer_thresholds = blackjack_config.DEALER_BET_THRESHOLDS

        return JSONResponse(
            content={
                "user_id": str(user_id),
                "balance": balance,
                "dealer_thresholds": dealer_thresholds,
            }
        )
    except Exception:
        log.error(f"获取用户 {user_id} 余额失败。", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get user balance")


@app.post("/api/game/bet")
async def place_bet(
    bet_request: BetRequest, user_id: int = Depends(get_current_user_id)
):
    """
    API: 玩家下注
    """
    bet_amount = bet_request.amount
    if bet_amount <= 0:
        raise HTTPException(status_code=400, detail="Bet amount must be positive")

    log.info(f"用户 {user_id} 正在下注 {bet_amount}")
    async with user_locks[user_id]:
        try:
            new_balance = await coin_service.remove_coins(
                user_id, bet_amount, "21点游戏下注"
            )
            if new_balance is None:
                log.warning(f"用户 {user_id} 下注失败，原因：余额不足。")
                raise HTTPException(status_code=402, detail="Insufficient funds")

            # --- 数据库持久化：创建游戏记录 ---
            game = await blackjack_service.create_game(user_id, bet_amount)
            if not game:
                log.warning(f"用户 {user_id} 下注失败，原因：已存在活跃游戏。")
                # 返还刚刚扣除的赌注
                await coin_service.add_coins(user_id, bet_amount, "21点重复下注退款")
                raise HTTPException(
                    status_code=409, detail="An active game already exists."
                )

            log.info(f"用户 {user_id} 下注成功。新余额: {new_balance}")
            return JSONResponse(
                content={"success": True, "new_balance": new_balance}, status_code=200
            )
        except Exception as e:
            log.error(f"为用户 {user_id} 处理下注时出错: {e}", exc_info=True)
            # 避免暴露内部错误细节
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail="Error placing bet")


@app.post("/api/game/double")
async def double_down(user_id: int = Depends(get_current_user_id)):
    """
    API: 玩家双倍下注
    """
    log.info(f"用户 {user_id} 正在双倍下注。")

    async with user_locks[user_id]:
        # --- 数据库持久化：获取游戏状态 ---
        game = await blackjack_service.get_active_game(user_id)
        if not game:
            log.warning(f"用户 {user_id} 试图在没有活跃赌注时双倍下注。")
            raise HTTPException(
                status_code=400, detail="No active bet to double down on."
            )

        if game.game_state != "active":
            log.warning(
                f"用户 {user_id} 试图在游戏状态为 '{game.game_state}' 时双倍下注。"
            )
            raise HTTPException(
                status_code=409, detail="You can only double down on the initial bet."
            )

        double_amount = game.bet_amount
        try:
            new_balance = await coin_service.remove_coins(
                user_id, double_amount, "21点游戏双倍下注"
            )
            if new_balance is None:
                log.warning(f"用户 {user_id} 双倍下注失败，原因：余额不足。")
                raise HTTPException(
                    status_code=402, detail="Insufficient funds to double down"
                )

            # --- 更新数据库中的游戏状态 ---
            updated_game = await blackjack_service.double_down(user_id, double_amount)
            log.info(
                f"用户 {user_id} 双倍下注成功。新总赌注: {updated_game.bet_amount}。新余额: {new_balance}"
            )
            return JSONResponse(
                content={"success": True, "new_balance": new_balance}, status_code=200
            )
        except Exception as e:
            log.error(f"为用户 {user_id} 处理双倍下注时出错: {e}", exc_info=True)
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail="Error processing double down")


@app.post("/api/game/payout")
async def give_payout(
    payout_request: PayoutRequest, user_id: int = Depends(get_current_user_id)
):
    """
    API: 游戏胜利派奖 (安全版本)
    """
    game_result = payout_request.result
    log.info(f"Processing payout for user {user_id} with result: {game_result}")

    async with user_locks[user_id]:
        # --- 安全支付流程 ---
        # 1. 获取当前游戏状态，但不删除它
        active_game = await blackjack_service.get_active_game(user_id)

        if active_game is None:
            log.warning(f"User {user_id} requested payout without an active game.")
            raise HTTPException(
                status_code=400, detail="No active bet found for this user."
            )

        final_bet = active_game.bet_amount

        # 2. 根据游戏结果计算派彩
        payout_amount = 0
        reason = "21点游戏结算"
        if game_result == "win":
            payout_amount = final_bet * 2  # 1:1 赔率
            reason = "21点游戏获胜"
        elif game_result == "blackjack":
            payout_amount = int(final_bet * 2.5)  # 3:2 赔率
            reason = "21点游戏Blackjack获胜"
        elif game_result == "push":
            payout_amount = final_bet  # 退还本金
            reason = "21点游戏平局"
        else:
            # 如果是 'lose' 或其他情况，不派彩，payout_amount 保持为 0
            log.info(f"User {user_id} lost their bet of {final_bet}. No payout.")
            payout_amount = 0
            reason = "21点游戏落败"

        if payout_amount < 0:
            # 这是一个理论上不应该发生的情况
            raise HTTPException(
                status_code=400, detail="Calculated payout cannot be negative"
            )

        # 3. 统一执行结算流程
        try:
            new_balance = active_game.bet_amount  # 默认为初始赌注

            if payout_amount > 0:
                log.info(
                    f"Paying out {payout_amount} to user {user_id} for a bet of {final_bet}"
                )
                new_balance = await coin_service.add_coins(
                    user_id, payout_amount, reason
                )
            else:
                # 如果是输了，不需要操作余额，直接获取当前余额
                new_balance = await coin_service.get_balance(user_id)

            # 4. 结算流程（支付或确认亏损）完成后，才安全删除游戏记录
            await blackjack_service.delete_game(user_id)

            log.info(
                f"User {user_id} game concluded. Result: {game_result}. New balance: {new_balance}"
            )
            return JSONResponse(
                content={"success": True, "new_balance": new_balance}, status_code=200
            )
        except Exception as e:
            log.error(f"CRITICAL: Payout failed for user {user_id}: {e}", exc_info=True)
            # 关键：此时游戏记录仍然存在于数据库中，不会造成资金损失
            log.warning(
                f"The active game for user {user_id} has been preserved for manual intervention."
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred during payout. Your bet is safe. Please contact an administrator.",
            )


# --- 静态文件服务 (仅在生产构建后生效) ---
static_files_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "src",
    "chat",
    "features",
    "games",
    "blackjack-web",
    "dist",
)

# 仅当dist目录存在时 (即前端已构建)，才挂载静态文件
if os.path.isdir(static_files_path):
    print(f"Serving static files from: {static_files_path}")
    # 将整个 dist 目录挂载为静态文件目录
    # html=True 参数会自动为根路径提供 index.html
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print(
        "INFO:     Frontend 'dist' directory not found. Static file serving is disabled."
    )
    print("INFO:     This is normal in development when using the Vite dev server.")


# 运行命令: uvicorn web.app:app --reload --port 8000
