import os
import httpx
import logging
import asyncio
from typing import List
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
from cachetools import TTLCache


class LockCache(TTLCache):
    """一个在键缺失时创建 asyncio.Lock 的 TTLCache。"""

    def __missing__(self, key):
        lock = asyncio.Lock()
        self[key] = lock
        return lock


# 创建一个TTL缓存来存储用户锁，TTL设置为1小时（3600秒）
# maxsize可以根据你的预计并发用户数进行调整
user_locks = LockCache(maxsize=1000, ttl=3600)


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


class PayoutRequest(BaseModel):
    result: str  # 'win', 'blackjack', 'push', 'loss'
    # 可选的游戏状态信息，用于验证
    player_hand: List[str] = None  # 玩家手牌
    dealer_hand: List[str] = None  # 庄家手牌
    deck_snapshot: List[str] = None  # 牌组快照


class GameStateRequest(BaseModel):
    player_hand: List[str]  # 玩家手牌
    dealer_hand: List[str]  # 庄家手牌
    deck_snapshot: List[str]  # 牌组快照
    game_result: str  # 'win', 'blackjack', 'push', 'loss'


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
            # --- 新增：在下注前，清理任何可能存在的遗留游戏 ---
            await blackjack_service.cleanup_legacy_game(user_id)

            # 🔒 关键安全检查：防止游戏中途下注
            active_game = await blackjack_service.get_active_game(user_id)
            if active_game:
                log.warning(
                    f"用户 {user_id} 试图在游戏进行中下注 {bet_amount}，当前游戏下注: {active_game.bet_amount}，已拒绝"
                )
                raise HTTPException(
                    status_code=409, detail="Cannot place bet while game is in progress"
                )

            new_balance = await coin_service.remove_coins(
                user_id, bet_amount, "21点游戏下注"
            )
            if new_balance is None:
                log.warning(f"用户 {user_id} 下注失败，原因：余额不足。")
                raise HTTPException(status_code=402, detail="Insufficient funds")

            # --- 数据库持久化：创建游戏记录 ---
            game = await blackjack_service.create_game(user_id, bet_amount)
            if not game:
                # 新逻辑：create_game 现在会处理遗留游戏，所以如果它返回None，
                # 这意味着一个无法自动解决的内部错误。
                log.error(f"为用户 {user_id} 创建游戏失败，可能是一个数据库问题。")
                # 返还赌注，因为游戏创建失败
                await coin_service.add_coins(
                    user_id, bet_amount, "21点游戏创建失败退款"
                )
                raise HTTPException(
                    status_code=500, detail="Failed to create a new game."
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

        return JSONResponse(
            content={"success": True, "message": "Game forfeited successfully."},
            status_code=200,
        )


@app.post("/api/game/payout")
async def give_payout(
    payout_request: PayoutRequest, user_id: int = Depends(get_current_user_id)
):
    """
    API: 游戏胜利派奖 (合并验证和结算)
    """
    game_result = payout_request.result
    log.info(f"Processing payout for user {user_id} with result: {game_result}")

    async with user_locks[user_id]:
        # --- 安全支付流程 ---
        # 1. 获取当前游戏状态，但不删除它
        active_game = await blackjack_service.get_active_game(user_id)

        if active_game is None:
            log.warning(
                f"用户 {user_id} 请求派彩，但未找到活跃游戏。这可能是重复的结算请求。"
            )
            raise HTTPException(
                status_code=400, detail="No active bet found for this user."
            )

        final_bet = active_game.bet_amount

        # 2. 验证游戏结果的有效性
        if game_result not in ["win", "blackjack", "push", "loss"]:
            log.warning(f"用户 {user_id} 提供了无效的游戏结果: {game_result}")
            raise HTTPException(status_code=400, detail="Invalid game result provided.")

        # 3. 如果提供了游戏状态信息，进行验证（可选）
        if (
            payout_request.player_hand
            and payout_request.dealer_hand
            and payout_request.deck_snapshot
        ):
            log.info(f"用户 {user_id} 提供了游戏状态，进行验证")

            # 计算手牌点数
            player_score = calculate_hand_score(payout_request.player_hand)
            dealer_score = calculate_hand_score(payout_request.dealer_hand)

            # 计算实际应该的结果
            actual_result = determine_actual_result(
                player_score,
                dealer_score,
                payout_request.player_hand,
                payout_request.dealer_hand,
            )

            # 记录验证日志
            log.info(
                f"游戏验证 - 用户: {user_id}, "
                f"玩家手牌: {payout_request.player_hand} (点数: {player_score}), "
                f"庄家手牌: {payout_request.dealer_hand} (点数: {dealer_score}), "
                f"报告结果: {game_result}, 实际结果: {actual_result}"
            )

            # 如果前端报告的结果与计算结果不符，使用服务器计算的结果
            if actual_result != game_result:
                log.warning(
                    f"用户 {user_id} 游戏结果不匹配: 报告={game_result}, 实际={actual_result}，使用服务器结果"
                )
                game_result = actual_result

        # 3. 根据游戏结果计算派彩
        payout_amount = 0
        reason = "21点游戏结算"
        if game_result == "win":
            payout_amount = final_bet * 2  # 1:1 赔率
            reason = "21点游戏获胜"
        elif game_result == "blackjack":
            payout_amount = int(final_bet * 1.5)  # 3:2 赔率
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

        # 4. 记录游戏结算日志
        log.info(
            f"用户 {user_id} 游戏结算: 结果={game_result}, 赌注={final_bet}, 派彩={payout_amount}"
        )

        # 5. 统一执行结算流程
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

            # 6. 结算流程（支付或确认亏损）完成后，才安全删除游戏记录
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


@app.post("/api/game/verify")
async def verify_game_state(
    game_state: GameStateRequest, user_id: int = Depends(get_current_user_id)
):
    """
    API: 验证游戏状态（防作弊）- 保留用于兼容性
    """
    log.info(f"Verifying game state for user {user_id}")

    async with user_locks[user_id]:
        # 检查是否有活跃游戏
        active_game = await blackjack_service.get_active_game(user_id)
        if not active_game:
            raise HTTPException(
                status_code=400, detail="No active game found for verification"
            )

        # 验证游戏结果的有效性
        if game_state.game_result not in ["win", "blackjack", "push", "loss"]:
            raise HTTPException(status_code=400, detail="Invalid game result provided")

        # 计算手牌点数
        player_score = calculate_hand_score(game_state.player_hand)
        dealer_score = calculate_hand_score(game_state.dealer_hand)

        # 计算实际应该的结果
        actual_result = determine_actual_result(
            player_score, dealer_score, game_state.player_hand, game_state.dealer_hand
        )

        # 记录验证日志
        log.info(
            f"游戏验证 - 用户: {user_id}, "
            f"玩家手牌: {game_state.player_hand} (点数: {player_score}), "
            f"庄家手牌: {game_state.dealer_hand} (点数: {dealer_score}), "
            f"报告结果: {game_state.game_result}, 实际结果: {actual_result}"
        )

        # 如果前端报告的结果与计算结果不符，记录警告
        if actual_result != game_state.game_result:
            log.warning(
                f"用户 {user_id} 游戏结果不匹配: 报告={game_state.game_result}, 实际={actual_result}"
            )
            return JSONResponse(
                content={
                    "valid": False,
                    "expected_result": actual_result,
                    "player_score": player_score,
                    "dealer_score": dealer_score,
                },
                status_code=200,
            )

        return JSONResponse(
            content={
                "valid": True,
                "player_score": player_score,
                "dealer_score": dealer_score,
            },
            status_code=200,
        )


def extract_card_rank(card: str) -> str:
    """安全提取牌面值，处理所有花色长度和格式"""
    if not card or not isinstance(card, str):
        raise ValueError(f"无效的牌: {card}")

    # 所有可能的花色前缀及其长度
    suits = {"Diamond": 7, "Heart": 5, "Spade": 5, "Club": 4}

    # 按长度降序排列，优先匹配长的花色（避免Diamond被误匹配）
    sorted_suits = sorted(suits.items(), key=lambda x: x[1], reverse=True)

    for suit_name, suit_length in sorted_suits:
        if card.startswith(suit_name):
            rank = card[suit_length:]
            # 验证提取的rank是否有效
            if rank in [
                "A",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "J",
                "Q",
                "K",
            ]:
                return rank
            else:
                raise ValueError(f"无效的牌面值: {card}, 提取的rank: {rank}")

    # 如果没有匹配到已知花色，尝试从末尾提取数字/字母
    # 备用逻辑：处理可能的异常格式
    if len(card) >= 1:
        rank = card[-1]
        if rank in ["A", "J", "Q", "K"]:
            return rank
        elif rank.isdigit():
            # 尝试提取最后两位数字（处理10）
            if len(card) >= 2 and card[-2].isdigit():
                rank = card[-2:]
                if rank == "10":
                    return rank
            return rank

    raise ValueError(f"无法解析的牌格式: {card}")


def calculate_hand_score(hand: List[str]) -> int:
    """计算手牌点数"""
    score = 0
    ace_count = 0

    for card in hand:
        try:
            rank = extract_card_rank(card)

            if rank in ["J", "Q", "K"]:
                score += 10
            elif rank == "A":
                score += 11
                ace_count += 1
            else:
                score += int(rank)
        except ValueError as e:
            log.warning(str(e))
            continue  # 跳过无效牌

    # 处理A的特殊情况
    while score > 21 and ace_count > 0:
        score -= 10
        ace_count -= 1

    return score


def determine_actual_result(
    player_score: int, dealer_score: int, player_hand: List[str], dealer_hand: List[str]
) -> str:
    """确定实际的游戏结果"""
    # 检查是否是Blackjack
    player_blackjack = len(player_hand) == 2 and player_score == 21
    dealer_blackjack = len(dealer_hand) == 2 and dealer_score == 21

    if player_blackjack and dealer_blackjack:
        return "push"
    elif player_blackjack:
        return "blackjack"
    elif dealer_blackjack:
        return "loss"
    elif player_score > 21:
        return "loss"
    elif dealer_score > 21:
        return "win"
    elif player_score > dealer_score:
        return "win"
    elif player_score < dealer_score:
        return "loss"
    else:
        return "push"


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
