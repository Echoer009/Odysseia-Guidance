import os
import httpx
import logging
import asyncio
from typing import List, Optional
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
from src.chat.utils.database import chat_db_manager

# 从根目录加载 .env 文件
load_dotenv(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".env")
)

app = FastAPI()
log = logging.getLogger(__name__)

# --- 用户操作锁，防止竞态条件 ---
from cachetools import TTLCache


class LockCache(TTLCache):
    """一个在键缺失时创建 asyncio.Lock 的 TTLCache。"""

    def __missing__(self, key):
        lock = asyncio.Lock()
        self[key] = lock
        return lock


# 创建一个TTL缓存来存储用户锁，TTL设置为30分钟（1800秒）
# 减少TTL时间以防止锁对象积累，maxsize设置为100以限制内存使用
user_locks = LockCache(maxsize=100, ttl=1800)


async def _record_game_result(bet_amount: int, payout_amount: int):
    """
    计算AI的净盈利并记录到数据库。
    - 如果玩家赢钱，AI的盈利为负。
    - 如果玩家输钱，AI的盈利为正。
    """
    try:
        net_win_loss = bet_amount - payout_amount
        await chat_db_manager.update_blackjack_net_win_loss(net_win_loss)
        log.info(f"已记录21点游戏结果到日报统计：AI净盈利 {net_win_loss}")
    except Exception as e:
        log.error(f"记录21点游戏结果到日报统计时出错: {e}", exc_info=True)


# --- 应用生命周期事件 ---
@app.on_event("startup")
async def startup_event():
    """在应用启动时初始化数据库表"""
    # --- 配置日志记录 ---
    # Uvicorn 默认的日志级别可能高于 INFO，导致我们自己的日志无法显示。
    # 在这里明确设置，以确保所有级别的日志都能在调试时看到。
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s"
    )

    log.info("Application startup: Initializing services...")

    # --- 新增：在初始化任何服务之前，首先连接数据库 ---
    from src.chat.utils.database import chat_db_manager

    await chat_db_manager.init_async()
    log.info("Database initialized.")

    await blackjack_service.initialize()
    log.info("Blackjack service initialized.")


@app.on_event("shutdown")
async def shutdown_event():
    """在应用关闭时断开数据库连接"""
    from src.chat.utils.database import chat_db_manager

    log.info("Application shutting down.")


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
# auto_error=False 允许多选的认证，这样在没有token时就不会自动触发403错误
auth_scheme = HTTPBearer(auto_error=False)

# 本地开发时使用的固定测试用户ID
TEST_USER_ID = 999999999999999999


async def get_current_user_id(
    token: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> int:
    """
    依赖项：从Bearer Token中获取用户信息并返回用户ID。
    在本地开发中，如果没有提供token，则返回一个固定的测试用户ID。
    """
    # 如果没有token（例如在本地开发环境中），返回测试用户ID
    if token is None:
        log.warning(f"未找到认证Token。回退到测试用户ID: {TEST_USER_ID}")
        return TEST_USER_ID

    # 如果有token，则执行原有的Discord API验证流程
    headers = {"Authorization": f"Bearer {token.credentials}"}
    log.info("正在从Discord API获取用户信息...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://discord.com/api/users/@me", headers=headers
            )
            response.raise_for_status()
            user_data = response.json()
            user_id = int(user_data["id"])
            log.info(f"成功识别用户: {user_data['username']} ({user_id})")
            return user_id
        except httpx.HTTPStatusError as e:
            log.error(
                f"从Discord API获取用户信息失败。状态码: {e.response.status_code}，"
                f"响应: {e.response.text}",
                exc_info=True,
            )
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        except httpx.RequestError as e:
            log.error(f"请求Discord API时发生网络错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Service Unavailable: Cannot connect to Discord API",
            )


class TokenRequest(BaseModel):
    code: str


class BetRequest(BaseModel):
    amount: int


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
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://discord.com/api/oauth2/token", data=data, headers=headers
            )
            response.raise_for_status()
            log.info("成功交换代码获取令牌。")
            return JSONResponse(content=response.json())
        except httpx.HTTPStatusError as e:
            log.error(
                f"与Discord API交换代码失败。状态码: {e.response.status_code}，"
                f"响应: {e.response.text}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="Failed to exchange code with Discord"
            )
        except httpx.RequestError as e:
            log.error(f"请求Discord API时发生网络错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Service Unavailable: Cannot connect to Discord API",
            )


@app.get("/api/user")
async def get_user_info(user_id: int = Depends(get_current_user_id)):
    """
    API: 获取当前用户信息，包括类脑币余额。
    """
    log.info(f"正在获取用户 {user_id} 的余额")
    try:
        # --- 新增：在加载游戏时，自动清理该用户任何卡住的旧游戏 ---
        balance = await coin_service.get_balance(user_id)

        # --- 本地开发专属：为测试用户自动创建账户并补充余额 ---
        if user_id == TEST_USER_ID and (balance is None or balance < 5000):
            amount_to_add = 10000 - (balance or 0)
            log.warning(
                f"测试用户 {user_id} 余额不足或不存在。正在补充 {amount_to_add} 硬币至10000。"
            )
            balance = await coin_service.add_coins(
                user_id, amount_to_add, "本地开发自动补充"
            )

        # --- 安全检查和日志记录 ---
        # 如果用户的余额记录因某种原因（例如数据异常）为空，这是一个严重问题
        if balance is None:
            log.critical(
                f"CRITICAL: 用户 {user_id} 的余额查询结果为 None，这表示数据库中可能存在数据损坏或异常。请立即检查 user_coins 表。"
            )
            # 返回一个明确的错误，而不是一个可能引起误解的 0
            raise HTTPException(
                status_code=500,
                detail="无法加载您的余额，您的账户数据可能存在异常。请联系管理员进行检查。",
            )

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


@app.post("/api/game/start")
async def start_game(
    bet_request: BetRequest, user_id: int = Depends(get_current_user_id)
):
    """
    API: 玩家下注并开始一个新游戏
    """
    bet_amount = bet_request.amount
    if bet_amount <= 0:
        raise HTTPException(status_code=400, detail="Bet amount must be positive")

    log.info(f"用户 {user_id} 正在下注 {bet_amount} 开始新游戏")
    async with user_locks[user_id]:
        # 检查并清理任何卡住的旧游戏
        if await blackjack_service.get_active_game(user_id):
            log.warning(
                f"用户 {user_id} 有一个正在进行的游戏。为了开始新游戏，旧游戏将被没收。"
            )
            await blackjack_service.delete_game(user_id)

        # 扣除赌注
        new_balance = await coin_service.remove_coins(
            user_id, bet_amount, "21点游戏下注"
        )
        if new_balance is None:
            raise HTTPException(status_code=402, detail="Insufficient funds")

        try:
            # 创建游戏
            game = await blackjack_service.start_game(user_id, bet_amount)

            # --- 新增：如果游戏在发牌时就已结束（例如21点），立即处理派彩 ---
            final_balance = new_balance
            if game.game_state.startswith("finished"):
                payout_amount = 0
                reason = "21点游戏结算"

                if game.game_state == "finished_blackjack":
                    payout_amount = int(game.bet_amount * 2.5)  # Blackjack 3:2赔率
                    reason = "21点游戏Blackjack获胜"
                elif game.game_state == "finished_push":
                    payout_amount = game.bet_amount  # 平局，退还赌注
                    reason = "21点游戏平局"
                # 注意: 'finished_loss' (庄家21点) 的派彩为0

                if payout_amount > 0:
                    final_balance = await coin_service.add_coins(
                        user_id, payout_amount, reason
                    )

                log.info(
                    f"用户 {user_id} 在发牌时结束游戏。结果: {game.game_state}。赌注: {game.bet_amount}。派彩: {payout_amount}。"
                )

                # 游戏已结束，立即删除记录
                await blackjack_service.delete_game(user_id)
                # --- 记录游戏结果 ---
                await _record_game_result(game.bet_amount, payout_amount)

            return JSONResponse(
                content={
                    "success": True,
                    "game": game.to_dict(),
                    "new_balance": final_balance,  # 返回更新后的余额
                }
            )
        except Exception as e:
            log.error(f"为用户 {user_id} 开始游戏时出错: {e}", exc_info=True)
            # 退还赌注
            await coin_service.add_coins(user_id, bet_amount, "21点游戏开始失败退款")
            raise HTTPException(status_code=500, detail="Could not start the game.")


# TODO: Re-implement double down with server-side logic


@app.post("/api/game/forfeit")
async def forfeit_game(user_id: int = Depends(get_current_user_id)):
    """
    API: 玩家放弃当前游戏
    用于解决玩家因任何原因（如网络断开、浏览器关闭）被卡在游戏中的问题。
    """
    log.warning(f"用户 {user_id} 正在请求放弃当前游戏。")
    async with user_locks[user_id]:
        active_game = await blackjack_service.get_active_game(user_id)
        if not active_game:
            log.info(f"用户 {user_id} 请求放弃游戏，但没有活跃游戏。")
            # 即使没有游戏，也返回成功，因为最终状态是一致的（没有活跃游戏）
            return JSONResponse(
                content={"success": True, "message": "No active game to forfeit."},
                status_code=200,
            )

        log.info(f"用户 {user_id} 已放弃赌注为 {active_game.bet_amount} 的游戏。")
        # 直接删除游戏记录，赌注不退还
        await blackjack_service.delete_game(user_id)

        # --- 记录游戏结果 ---
        await _record_game_result(active_game.bet_amount, 0)  # 投降，派彩为0

        return JSONResponse(
            content={"success": True, "message": "Game forfeited successfully."},
            status_code=200,
        )


@app.post("/api/game/double")
async def double_down(user_id: int = Depends(get_current_user_id)):
    """API: 玩家双倍下注"""
    async with user_locks[user_id]:
        game = await blackjack_service.get_active_game(user_id)
        if not game:
            raise HTTPException(
                status_code=400, detail="No active game to double down on."
            )

        if len(game.player_hand) != 2:
            raise HTTPException(
                status_code=409,
                detail="You can only double down on your initial two cards.",
            )

        double_amount = game.bet_amount
        new_balance = await coin_service.remove_coins(
            user_id, double_amount, "21点游戏双倍下注"
        )
        if new_balance is None:
            raise HTTPException(
                status_code=402, detail="Insufficient funds to double down."
            )

        try:
            game = await blackjack_service.double_down(user_id, double_amount)

            payout_amount = 0
            reason = "21点游戏结算"

            if game.game_state == "finished_win":
                payout_amount = game.bet_amount * 2
                reason = "21点游戏获胜"
            elif game.game_state == "finished_blackjack":
                payout_amount = int(game.bet_amount * 2.5)
                reason = "21点游戏Blackjack获胜"
            elif game.game_state == "finished_push":
                payout_amount = game.bet_amount
                reason = "21点游戏平局"

            final_balance = new_balance
            if payout_amount > 0:
                final_balance = await coin_service.add_coins(
                    user_id, payout_amount, reason
                )

            log.info(
                f"User {user_id} doubled down. Result: {game.game_state}. New Bet: {game.bet_amount}. Payout: {payout_amount}."
            )

            await blackjack_service.delete_game(user_id)

            # --- 记录游戏结果 ---
            await _record_game_result(game.bet_amount, payout_amount)

            return JSONResponse(
                content={
                    "success": True,
                    "game": game.to_dict(),
                    "new_balance": final_balance,
                }
            )
        except ValueError as e:
            await coin_service.add_coins(user_id, double_amount, "21点双倍下注失败退款")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            await coin_service.add_coins(user_id, double_amount, "21点双倍下注失败退款")
            log.error(
                f"Error during double down for user {user_id}: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred during the double down action.",
            )


@app.post("/api/game/hit")
async def player_hit(user_id: int = Depends(get_current_user_id)):
    """API: 玩家要牌"""
    async with user_locks[user_id]:
        try:
            game = await blackjack_service.player_hit(user_id)
            new_balance = await coin_service.get_balance(user_id)

            # 如果玩家爆牌，游戏结束并结算
            if game.game_state == "finished_loss":
                log.info(f"User {user_id} busted. Bet of {game.bet_amount} lost.")
                await blackjack_service.delete_game(user_id)
                # --- 记录游戏结果 ---
                await _record_game_result(game.bet_amount, 0)  # 爆牌，派彩为0
                return JSONResponse(
                    content={
                        "success": True,
                        "game": game.to_dict(),
                        "new_balance": new_balance,
                    }
                )

            return JSONResponse(content={"success": True, "game": game.to_dict()})
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log.error(f"Error during player hit for user {user_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="An error occurred during the hit action."
            )


@app.post("/api/game/stand")
async def player_stand(user_id: int = Depends(get_current_user_id)):
    """API: 玩家停牌，庄家行动并结算"""
    async with user_locks[user_id]:
        try:
            game = await blackjack_service.player_stand(user_id)

            payout_amount = 0
            reason = "21点游戏结算"

            if game.game_state == "finished_win":
                payout_amount = game.bet_amount * 2
                reason = "21点游戏获胜"
            elif game.game_state == "finished_blackjack":
                payout_amount = int(game.bet_amount * 2.5)  # Blackjack 3:2
                reason = "21点游戏Blackjack获胜"
            elif game.game_state == "finished_push":
                payout_amount = game.bet_amount
                reason = "21点游戏平局"
            # 'finished_loss' has a payout_amount of 0

            new_balance = await coin_service.get_balance(user_id)
            if payout_amount > 0:
                new_balance = await coin_service.add_coins(
                    user_id, payout_amount, reason
                )

            log.info(
                f"User {user_id} finished game. Result: {game.game_state}. Bet: {game.bet_amount}. Payout: {payout_amount}."
            )

            # 游戏结束，删除记录
            await blackjack_service.delete_game(user_id)

            # --- 记录游戏结果 ---
            await _record_game_result(game.bet_amount, payout_amount)

            return JSONResponse(
                content={
                    "success": True,
                    "game": game.to_dict(),
                    "new_balance": new_balance,
                }
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            log.error(
                f"Error during player stand for user {user_id}: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail="An error occurred during the stand action."
            )


# --- 静态文件服务 (仅在生产构建后生效) ---
static_files_path = os.path.join(
    os.path.dirname(__file__),
    "dist",
)

# 仅当dist目录存在时 (即前端已构建)，才挂재静态文件
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


# 运行命令: uvicorn src.chat.features.games.blackjack-web.app:app --reload --port 8000
