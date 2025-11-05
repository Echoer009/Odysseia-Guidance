import os
import requests
import logging
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

# --- 类脑币服务 ---
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.games.config import blackjack_config

# 从根目录加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI()
log = logging.getLogger(__name__)


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
    log.info("Fetching user info from Discord API...")
    try:
        response = requests.get("https://discord.com/api/users/@me", headers=headers)
        response.raise_for_status()
        user_data = response.json()
        user_id = int(user_data["id"])
        log.info(f"Successfully identified user: {user_data['username']} ({user_id})")
        return user_id
    except requests.exceptions.RequestException as e:
        log.error("Failed to fetch user from Discord API.", exc_info=True)
        if e.response is not None:
            log.error(f"Discord API response status: {e.response.status_code}")
            log.error(f"Discord API response body: {e.response.text}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class TokenRequest(BaseModel):
    code: str


class BetRequest(BaseModel):
    amount: int


class PayoutRequest(BaseModel):
    amount: int


@app.post("/api/token")
async def exchange_code_for_token(request: TokenRequest):
    """API: 用Discord返回的code换取access_token"""
    log.info(f"Received token exchange request with code: '{request.code[:10]}...'")
    client_id = os.getenv("VITE_DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")

    if not client_id or not client_secret:
        log.error("Server is missing VITE_DISCORD_CLIENT_ID or DISCORD_CLIENT_SECRET")
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

    log.info("Sending request to Discord API for token exchange...")
    try:
        response = requests.post(
            "https://discord.com/api/oauth2/token", data=data, headers=headers
        )
        response.raise_for_status()
        log.info("Successfully exchanged code for token.")
        return JSONResponse(content=response.json())
    except requests.exceptions.RequestException as e:
        log.error("Failed to exchange code with Discord API.", exc_info=True)
        if e.response is not None:
            log.error(f"Discord API response status: {e.response.status_code}")
            log.error(f"Discord API response body: {e.response.text}")
        raise HTTPException(
            status_code=500, detail="Failed to exchange code with Discord"
        )


@app.get("/api/user")
async def get_user_info(user_id: int = Depends(get_current_user_id)):
    """
    API: 获取当前用户信息，包括类脑币余额。
    """
    log.info(f"Fetching balance for user_id: {user_id}")
    try:
        balance = await coin_service.get_balance(user_id)
        log.info(f"User {user_id} balance is {balance}")

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
        log.error(f"Failed to get balance for user {user_id}.", exc_info=True)
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

    log.info(f"User {user_id} is betting {bet_amount}")
    try:
        new_balance = await coin_service.remove_coins(
            user_id, bet_amount, "21点游戏下注"
        )
        if new_balance is None:
            log.warning(f"User {user_id} bet failed due to insufficient funds.")
            raise HTTPException(status_code=402, detail="Insufficient funds")

        log.info(f"User {user_id} bet successful. New balance: {new_balance}")
        return JSONResponse(
            content={"success": True, "new_balance": new_balance}, status_code=200
        )
    except Exception as e:
        log.error(f"Error placing bet for user {user_id}: {e}", exc_info=True)
        # 避免暴露内部错误细节
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Error placing bet")


@app.post("/api/game/payout")
async def give_payout(
    payout_request: PayoutRequest, user_id: int = Depends(get_current_user_id)
):
    """
    API: 游戏胜利派奖
    """
    payout_amount = payout_request.amount
    if payout_amount <= 0:
        raise HTTPException(status_code=400, detail="Payout amount must be positive")

    log.info(f"Paying out {payout_amount} to user {user_id}")
    try:
        new_balance = await coin_service.add_coins(
            user_id, payout_amount, "21点游戏获胜"
        )
        log.info(f"User {user_id} payout successful. New balance: {new_balance}")
        return JSONResponse(
            content={"success": True, "new_balance": new_balance}, status_code=200
        )
    except Exception as e:
        log.error(f"Error giving payout to user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error giving payout")


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
