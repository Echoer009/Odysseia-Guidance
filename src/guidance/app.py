import os
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".env")
)

app = FastAPI(title="Odysseia Guidance", version="1.0.0")
log = logging.getLogger(__name__)

auth_scheme = HTTPBearer(auto_error=False)
TEST_USER_ID = 999999999999999999


@app.on_event("startup")
async def startup_event():
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s"
    )
    log.info("Guidance app startup.")


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
        raise


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
            log.info(
                f"成功识别用户: {user_data.get('username', 'unknown')} ({user_id})"
            )
            return user_id
        except httpx.HTTPStatusError as e:
            log.error(
                f"从Discord API获取用户信息失败。状态码: {e.response.status_code}",
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


@app.post("/api/token")
async def exchange_code_for_token(request: TokenRequest):
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
                f"与Discord API交换代码失败。状态码: {e.response.status_code}",
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


GUILD_ID = os.getenv("GUILD_ID", "1234431460159160360")


async def get_guild_nickname(user_id: int) -> Optional[str]:
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
            member_data = response.json()
            nick = member_data.get("nick")
            if nick:
                return nick
            return member_data.get("user", {}).get("global_name") or member_data.get(
                "user", {}
            ).get("username")
        except Exception as e:
            log.warning(f"获取服务器昵称失败: {e}")
            return None


@app.get("/api/user")
async def get_user_info(user_id: int = Depends(get_current_user_id)):
    log.info(f"获取用户 {user_id} 信息")
    username = None
    if user_id == TEST_USER_ID:
        username = f"旅行者_{user_id % 10000}"
    else:
        nickname = await get_guild_nickname(user_id)
        if nickname:
            username = nickname
    return JSONResponse(content={"user_id": str(user_id), "username": username})


static_files_path = os.path.join(os.path.dirname(__file__), "dist")

if os.path.isdir(static_files_path):
    print(f"Serving static files from: {static_files_path}")
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print(
        "INFO:     Frontend 'dist' directory not found. Static file serving is disabled."
    )
    print("INFO:     This is normal in development when using the Vite dev server.")


# 运行命令: uvicorn src.guidance.app:app --reload --port 8000
