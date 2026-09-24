import os
import json
import random
import sqlite3
import asyncio
import logging
from functools import partial
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone, timedelta

import httpx
from cachetools import TTLCache
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- 类脑币服务 ---
from src.chat.features.odysseia_coin.service.coin_service import coin_service

# 从根目录加载 .env 文件
load_dotenv(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".env")
)

app = FastAPI()
log = logging.getLogger(__name__)

# --- 本地预览模式（不影响生产）：RIDDLE_DEV_MODE=1 时无 token 的请求使用固定预览用户 ---
RIDDLE_DEV_MODE = os.getenv("RIDDLE_DEV_MODE") == "1"
RIDDLE_DEV_USER_ID = 999999

# --- 游戏常量 ---
MAX_DAILY_RIDDLES = 15  # 每日最多领取的灯谜数
MAX_DAILY_SWAPS = 3  # 每日换题次数上限
BASE_REWARD = 80  # 答对基础奖励
STREAK_BONUS = 20  # 每连对一题的额外奖励
MAX_REWARD = 200  # 单题奖励上限
HINT_AFTER_WRONG = 3  # 答错几次后给出提示
SWAP_LOG_ID = "__swap__"  # riddle_log 中标记"换题"事件的哨兵 ID

# --- 题库加载 ---
RIDDLES_FILE = os.path.join(os.path.dirname(__file__), "riddles.json")
with open(RIDDLES_FILE, "r", encoding="utf-8") as _f:
    RIDDLES: List[Dict[str, str]] = json.load(_f)
RIDDLES_BY_ID: Dict[str, Dict[str, str]] = {r["id"]: r for r in RIDDLES}


# --- 北京时间辅助 ---
def get_beijing_today_str() -> str:
    """获取北京时间（UTC+8）的当前日期字符串，格式为 YYYY-MM-DD。"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d")


def _beijing_now_str() -> str:
    """北京时间的当前时间字符串，格式为 YYYY-MM-DD HH:MM:SS。"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")


# --- 独立的 SQLite 管理器 (data/riddle.db) ---
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
)
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "riddle.db")


class RiddleDatabaseManager:
    """灯谜游戏的轻量级异步 SQLite 管理器（独立于 chat_db_manager 的 riddle.db）。

    参考 src/chat/utils/database.py 的 _db_transaction 模式：
    每次操作都在线程池中用一个全新的连接执行，保证线程隔离。
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def _execute(self, func: Callable, *args, **kwargs) -> Any:
        """在线程池中执行一个同步的数据库操作。"""
        blocking_task = partial(func, *args, **kwargs)
        return await asyncio.get_running_loop().run_in_executor(None, blocking_task)

    def _init_database_logic(self):
        """包含所有同步数据库初始化逻辑的方法。"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            # --- 游戏状态表 ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS riddle_game_states (
                    user_id INTEGER PRIMARY KEY,
                    current_riddle_id TEXT,
                    wrong_count INTEGER NOT NULL DEFAULT 0,
                    streak INTEGER NOT NULL DEFAULT 0,
                    daily_count INTEGER NOT NULL DEFAULT 0,
                    daily_date TEXT NOT NULL DEFAULT '',
                    total_solved INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            # --- 游戏日志表 ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS riddle_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    riddle_id TEXT NOT NULL,
                    solved INTEGER NOT NULL DEFAULT 0,
                    coins_delta INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_riddle_log_user_time"
                " ON riddle_log (user_id, created_at);"
            )
            conn.commit()
            log.info(f"灯谜数据库表在 {self.db_path} 同步初始化成功。")
        except sqlite3.Error as e:
            log.error(f"同步初始化灯谜数据库表时出错: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def _db_transaction(
        self,
        query: str,
        params: Any = (),
        *,
        fetch: str = "none",
        commit: bool = False,
    ):
        """一个完全线程安全的同步事务函数，为每个操作创建新的连接。"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)

            if fetch == "one":
                result = cursor.fetchone()
            elif fetch == "all":
                result = cursor.fetchall()
            elif fetch == "lastrowid":
                result = cursor.lastrowid
            elif fetch == "rowcount":
                result = cursor.rowcount
            else:
                result = None

            if commit:
                conn.commit()
            return result
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            log.error(f"灯谜数据库事务失败，已回滚: {e} | Query: {query}")
            raise
        finally:
            if conn:
                conn.close()

    async def init_async(self):
        """异步初始化数据库，在事件循环中运行同步的建表逻辑。"""
        log.info("开始异步灯谜数据库初始化...")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        await self._execute(self._init_database_logic)
        log.info("异步灯谜数据库初始化完成。")

    async def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM riddle_game_states WHERE user_id = ?"
        row = await self._execute(self._db_transaction, query, (user_id,), fetch="one")
        return dict(row) if row else None

    async def upsert_state(self, state: Dict[str, Any]) -> None:
        query = """
            INSERT INTO riddle_game_states
                (user_id, current_riddle_id, wrong_count, streak, daily_count, daily_date, total_solved)
            VALUES
                (:user_id, :current_riddle_id, :wrong_count, :streak, :daily_count, :daily_date, :total_solved)
            ON CONFLICT(user_id) DO UPDATE SET
                current_riddle_id = excluded.current_riddle_id,
                wrong_count = excluded.wrong_count,
                streak = excluded.streak,
                daily_count = excluded.daily_count,
                daily_date = excluded.daily_date,
                total_solved = excluded.total_solved;
        """
        await self._execute(self._db_transaction, query, state, commit=True)

    async def count_swaps_today(self, user_id: int) -> int:
        """统计用户今日（北京时间）的换题次数。"""
        query = (
            "SELECT COUNT(*) AS c FROM riddle_log"
            " WHERE user_id = ? AND riddle_id = ? AND substr(created_at, 1, 10) = ?"
        )
        row = await self._execute(
            self._db_transaction,
            query,
            (user_id, SWAP_LOG_ID, get_beijing_today_str()),
            fetch="one",
        )
        return row["c"] if row else 0

    async def add_log(
        self, user_id: int, riddle_id: str, solved: int, coins_delta: int
    ) -> None:
        query = (
            "INSERT INTO riddle_log (user_id, riddle_id, solved, coins_delta, created_at)"
            " VALUES (?, ?, ?, ?, ?)"
        )
        await self._execute(
            self._db_transaction,
            query,
            (user_id, riddle_id, solved, coins_delta, _beijing_now_str()),
            commit=True,
        )

    async def get_leaderboard(self) -> List[Dict[str, Any]]:
        query = (
            "SELECT user_id, total_solved, streak FROM riddle_game_states"
            " WHERE total_solved > 0"
            " ORDER BY total_solved DESC, streak DESC LIMIT 10"
        )
        rows = await self._execute(self._db_transaction, query, fetch="all")
        return [dict(r) for r in rows] if rows else []


riddle_db = RiddleDatabaseManager()


# --- 用户操作锁，防止竞态条件 ---
class LockCache(TTLCache):
    """一个在键缺失时创建 asyncio.Lock 的 TTLCache。"""

    def __missing__(self, key):
        lock = asyncio.Lock()
        self[key] = lock
        return lock


# 创建一个TTL缓存来存储用户锁，TTL设置为30分钟（1800秒）
user_locks = LockCache(maxsize=100, ttl=1800)


# --- 游戏状态辅助 ---
async def _load_user_state(user_id: int) -> Dict[str, Any]:
    """加载用户状态；跨天（北京时间）时自动重置每日计数。"""
    state = await riddle_db.get_state(user_id)
    today = get_beijing_today_str()
    if state is None:
        return {
            "user_id": user_id,
            "current_riddle_id": None,
            "wrong_count": 0,
            "streak": 0,
            "daily_count": 0,
            "daily_date": today,
            "total_solved": 0,
        }
    if state["daily_date"] != today:
        state["daily_count"] = 0
        state["daily_date"] = today
        await riddle_db.upsert_state(state)
    return state


def _serialize_state(state: Dict[str, Any], balance: Optional[int]) -> Dict[str, Any]:
    """把内部状态序列化成 API 响应（绝不包含谜底）。"""
    riddle = RIDDLES_BY_ID.get(state.get("current_riddle_id") or "")
    hint = (
        riddle["hint"]
        if riddle and state["wrong_count"] >= HINT_AFTER_WRONG
        else None
    )
    return {
        "user_id": str(state["user_id"]),
        "has_riddle": riddle is not None,
        "riddle_id": riddle["id"] if riddle else None,
        "question": riddle["question"] if riddle else None,
        "wrong_count": state["wrong_count"],
        "hint": hint,
        "streak": state["streak"],
        "daily_remaining": max(0, MAX_DAILY_RIDDLES - state["daily_count"]),
        "total_solved": state["total_solved"],
        "balance": balance,
    }


def _pick_riddle(exclude_id: Optional[str]) -> Dict[str, str]:
    """随机抽一题，尽量避免与当前题重复。"""
    pool = [r for r in RIDDLES if r["id"] != exclude_id] or RIDDLES
    return random.choice(pool)


def _normalize_answer(text: str) -> str:
    """大小写与空白不敏感的答案规范化。"""
    return "".join(text.split()).casefold()


# --- 应用生命周期事件 ---
@app.on_event("startup")
async def startup_event():
    """在应用启动时初始化数据库表"""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s"
    )
    log.info("Application startup: Initializing riddle services...")
    await riddle_db.init_async()
    log.info(
        f"Riddle database initialized at {DB_PATH} ({len(RIDDLES)} riddles loaded)."
    )


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭"""
    log.info("Riddle application shutting down.")


# --- 中间件：添加详细的请求日志 ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 本地预览（无 Caddy 剥前缀）：把 /riddle/api/* 重写为 /api/* 交给 API 路由
    path = request.scope.get("path", "")
    if path.startswith("/riddle/api/"):
        request.scope["path"] = path[len("/riddle"):]
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
        raise


# --- 安全性和依赖 ---
# auto_error=False 允许多选的认证，这样在没有token时就不会自动触发403错误
auth_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    token: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> int:
    """
    依赖项：从Bearer Token中获取用户信息并返回用户ID。
    """
    if token is None:
        if RIDDLE_DEV_MODE:
            return RIDDLE_DEV_USER_ID
        raise HTTPException(status_code=401, detail="Missing authentication token")

    # 如果有token，则执行Discord API验证流程
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


class AnswerRequest(BaseModel):
    text: str


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


async def _safe_balance(user_id: int) -> Optional[int]:
    """获取用户余额，失败时返回 None（预览模式下本地数据库可能不可用）。"""
    try:
        return await coin_service.get_balance(user_id)
    except Exception as e:
        log.warning(f"获取用户 {user_id} 余额失败: {e}")
        return None


# --- 游戏状态 ---
@app.get("/api/riddle/state")
async def get_riddle_state(user_id: int = Depends(get_current_user_id)):
    """API: 当前状态 + 题目（不含答案） + 连对数 + 今日剩余次数"""
    log.info(f"正在获取用户 {user_id} 的灯谜状态")
    try:
        async with user_locks[user_id]:
            state = await _load_user_state(user_id)
            balance = await _safe_balance(user_id)
            return JSONResponse(
                content={"success": True, "state": _serialize_state(state, balance)}
            )
    except HTTPException:
        raise
    except Exception:
        log.error(f"获取用户 {user_id} 灯谜状态失败。", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get riddle state")


@app.post("/api/riddle/start")
async def start_riddle(user_id: int = Depends(get_current_user_id)):
    """API: 开始新题 / 换题（换题每日限 3 次，总题数每日限 15 题）"""
    async with user_locks[user_id]:
        state = await _load_user_state(user_id)

        if state["daily_count"] >= MAX_DAILY_RIDDLES:
            raise HTTPException(
                status_code=429,
                detail=f"今天的 {MAX_DAILY_RIDDLES} 道灯谜已经猜完啦，明月不改，明天再来！",
            )

        current_id = state.get("current_riddle_id")
        if current_id:
            # 已有进行中的题 => 视为换题
            swaps_today = await riddle_db.count_swaps_today(user_id)
            if swaps_today >= MAX_DAILY_SWAPS:
                raise HTTPException(
                    status_code=429,
                    detail=f"今日换题次数已用完（最多 {MAX_DAILY_SWAPS} 次），安心猜这一题吧！",
                )
            await riddle_db.add_log(user_id, SWAP_LOG_ID, 0, 0)
            state["streak"] = 0  # 换题视为放弃当前题，连对清零

        new_riddle = _pick_riddle(current_id)
        state["current_riddle_id"] = new_riddle["id"]
        state["wrong_count"] = 0
        state["daily_count"] += 1
        await riddle_db.upsert_state(state)

        balance = await _safe_balance(user_id)
        log.info(
            f"用户 {user_id} {'换题' if current_id else '开始新题'}: {new_riddle['id']}"
            f" (今日已用 {state['daily_count']}/{MAX_DAILY_RIDDLES})"
        )
        return JSONResponse(
            content={"success": True, "state": _serialize_state(state, balance)}
        )


@app.post("/api/riddle/answer")
async def answer_riddle(
    request: AnswerRequest, user_id: int = Depends(get_current_user_id)
):
    """API: 提交答案（大小写/空白不敏感的精确匹配）"""
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="答案不能为空")

    async with user_locks[user_id]:
        state = await _load_user_state(user_id)
        riddle = RIDDLES_BY_ID.get(state.get("current_riddle_id") or "")
        if not riddle:
            raise HTTPException(
                status_code=400, detail="当前没有进行中的灯谜，请先开始一题"
            )

        if _normalize_answer(text) == _normalize_answer(riddle["answer"]):
            # --- 答对：按连对计算奖励 ---
            new_streak = state["streak"] + 1
            reward = min(BASE_REWARD + (new_streak - 1) * STREAK_BONUS, MAX_REWARD)
            new_balance = None
            if RIDDLE_DEV_MODE:
                log.info(f"预览模式：跳过为用户 {user_id} 发放 {reward} 类脑币")
            else:
                try:
                    new_balance = await coin_service.add_coins(
                        user_id, reward, "猜灯谜奖励"
                    )
                except Exception as e:
                    log.error(
                        f"为用户 {user_id} 发放猜灯谜奖励失败: {e}", exc_info=True
                    )
                    raise HTTPException(status_code=500, detail="奖励发放失败，请稍后重试")

            state["streak"] = new_streak
            state["total_solved"] += 1
            state["current_riddle_id"] = None
            state["wrong_count"] = 0
            await riddle_db.upsert_state(state)
            await riddle_db.add_log(user_id, riddle["id"], 1, reward)
            log.info(
                f"用户 {user_id} 答对灯谜 {riddle['id']}，连对 {new_streak}，奖励 {reward}。"
            )
            return JSONResponse(
                content={
                    "success": True,
                    "correct": True,
                    "answer": riddle["answer"],
                    "reward": reward,
                    "new_balance": new_balance,
                    "state": _serialize_state(state, new_balance),
                }
            )

        # --- 答错 ---
        state["wrong_count"] += 1
        await riddle_db.upsert_state(state)
        show_hint = state["wrong_count"] >= HINT_AFTER_WRONG
        balance = await _safe_balance(user_id)
        return JSONResponse(
            content={
                "success": True,
                "correct": False,
                "wrong_count": state["wrong_count"],
                "hint": riddle["hint"] if show_hint else None,
                "state": _serialize_state(state, balance),
            }
        )


@app.post("/api/riddle/giveup")
async def giveup_riddle(user_id: int = Depends(get_current_user_id)):
    """API: 放弃当前题，连对清零"""
    async with user_locks[user_id]:
        state = await _load_user_state(user_id)
        riddle = RIDDLES_BY_ID.get(state.get("current_riddle_id") or "")
        if not riddle:
            balance = await _safe_balance(user_id)
            return JSONResponse(
                content={
                    "success": True,
                    "message": "No active riddle.",
                    "state": _serialize_state(state, balance),
                }
            )

        state["current_riddle_id"] = None
        state["wrong_count"] = 0
        state["streak"] = 0
        await riddle_db.upsert_state(state)
        await riddle_db.add_log(user_id, riddle["id"], 0, 0)
        balance = await _safe_balance(user_id)
        log.info(f"用户 {user_id} 放弃灯谜 {riddle['id']}，连对清零。")
        return JSONResponse(
            content={
                "success": True,
                "answer": riddle["answer"],
                "state": _serialize_state(state, balance),
            }
        )


@app.get("/api/riddle/leaderboard")
async def get_leaderboard(user_id: int = Depends(get_current_user_id)):
    """API: 按 total_solved 排序的前 10 名"""
    try:
        rows = await riddle_db.get_leaderboard()
        return JSONResponse(
            content={
                "success": True,
                "leaderboard": [
                    {
                        "user_id": str(r["user_id"]),
                        "solved": r["total_solved"],
                        "streak": r["streak"],
                    }
                    for r in rows
                ],
            }
        )
    except Exception:
        log.error("获取灯谜排行榜失败。", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get leaderboard")


# --- 静态文件服务 (仅在生产构建后生效) ---
static_files_path = os.path.join(
    os.path.dirname(__file__),
    "dist",
)

# 仅当dist目录存在时 (即前端已构建)，才挂载静态文件
if os.path.isdir(static_files_path):
    print(f"Serving static files from: {static_files_path}")
    # 将整个 dist 目录挂载为静态文件目录
    # html=True 参数会自动为根路径提供 index.html
    # /riddle 前缀挂载用于本地预览（前端 base 为 /riddle/）
    app.mount("/riddle", StaticFiles(directory=static_files_path, html=True), name="static_riddle")
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print(
        "INFO:     Frontend 'dist' directory not found. Static file serving is disabled."
    )
    print("INFO:     This is normal in development when using the Vite dev server.")


# 运行命令: uvicorn src.chat.features.games.riddle-web.app:app --reload --port 8005
