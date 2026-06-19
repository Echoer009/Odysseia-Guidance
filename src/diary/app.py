# -*- coding: utf-8 -*-
"""
类脑娘的日记 - FastAPI 应用。
前端 (Vue3) 在 dist/ 下，由本服务挂载静态文件提供。
后端提供: Discord 鉴权、/api/diary (结构化日记数据)。
背景旋律 (BGM) 直接硬编码在前端 public/audio/ 下，不走后端。

运行: uvicorn src.diary.app:app --host 0.0.0.0 --port 8003
"""

import os
import logging
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

from src.diary.services.diary_service import get_diary
from src.chat.utils.database import chat_db_manager

load_dotenv()

app = FastAPI(title="Odysseia Diary", version="1.0.0")
log = logging.getLogger(__name__)

auth_scheme = HTTPBearer(auto_error=False)
TEST_USER_ID = 999999999999999999


@app.on_event("startup")
async def startup_event():
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s"
    )
    await chat_db_manager.init_async()
    log.info("Diary app startup.")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    log.info(f"收到请求: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        log.info(
            f"请求完成: {request.method} {request.url.path} - {response.status_code}"
        )
        return response
    except Exception as e:
        log.error(
            f"请求处理出错: {request.method} {request.url.path} - {e}",
            exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# 鉴权 (与 guidance/blackjack 一致)
# ---------------------------------------------------------------------------

async def get_current_user_id(
    token: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> int:
    if token is None:
        log.warning(f"未找到认证Token。回退到测试用户ID: {TEST_USER_ID}")
        return TEST_USER_ID

    headers = {"Authorization": f"Bearer {token.credentials}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://discord.com/api/users/@me", headers=headers
            )
            response.raise_for_status()
            user_data = response.json()
            user_id = int(user_data["id"])
            log.info(f"成功识别用户: {user_data.get('username')} ({user_id})")
            return user_id
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Service Unavailable: Cannot connect to Discord API",
            )


from pydantic import BaseModel


class CodeIn(BaseModel):
    code: str


@app.post("/api/token")
async def exchange_code_for_token(req: CodeIn):
    log.info(f"收到令牌交换请求，代码: '{req.code[:10]}...'")
    client_id = os.getenv("VITE_DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Server is missing Discord credentials")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": req.code,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://discord.com/api/oauth2/token", data=data, headers=headers
            )
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=500, detail="Failed to exchange code with Discord")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Cannot connect to Discord API")


GUILD_ID = os.getenv("GUILD_ID", "0").split(",")[0].strip()


async def _get_guild_nickname(user_id: int) -> Optional[str]:
    bot_token = os.getenv("DISCORD_TOKEN")
    if not bot_token:
        return None
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://discord.com/api/guilds/{GUILD_ID}/members/{user_id}",
                headers={"Authorization": f"Bot {bot_token}"},
            )
            response.raise_for_status()
            member = response.json()
            return member.get("nick") or member.get("user", {}).get("global_name") or member.get("user", {}).get("username")
        except Exception as e:
            log.warning(f"获取服务器昵称失败: {e}")
            return None


@app.get("/api/user")
async def get_user_info(user_id: int = Depends(get_current_user_id)):
    username = None
    if user_id == TEST_USER_ID:
        username = f"旅行者_{user_id % 10000}"
    else:
        nickname = await _get_guild_nickname(user_id)
        if nickname:
            username = nickname
    return JSONResponse(content={"user_id": str(user_id), "username": username})


# ---------------------------------------------------------------------------
# 日记数据
# ---------------------------------------------------------------------------

@app.get("/api/diary")
async def api_diary():
    try:
        diary = await get_diary()
        return JSONResponse(content=diary)
    except Exception as e:
        log.error(f"获取日记数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to build diary")


# ---------------------------------------------------------------------------
# 静态文件 (前端 dist)
# ---------------------------------------------------------------------------

static_files_path = os.path.join(os.path.dirname(__file__), "dist")

if os.path.isdir(static_files_path):
    print(f"Serving static files from: {static_files_path}")
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print("INFO:     Frontend 'dist' directory not found. Static file serving is disabled.")
    print("INFO:     This is normal in development when using the Vite dev server.")
