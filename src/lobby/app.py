import os
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env"))

app = FastAPI(title="Odysseia Lobby", version="1.0.0")
log = logging.getLogger(__name__)

auth_scheme = HTTPBearer(auto_error=False)
TEST_USER_ID = 999999999999999999


@app.on_event("startup")
async def startup_event():
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s"
    )
    log.info("Lobby app startup.")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    log.info(f"[Lobby] {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        log.info(
            f"[Lobby] {request.method} {request.url.path} - {response.status_code}"
        )
        return response
    except Exception as e:
        log.error(f"[Lobby] {request.method} {request.url.path} - {e}", exc_info=True)
        raise


async def get_current_user_id(
    token: Optional[HTTPAuthorizationCredentials],
) -> Optional[int]:
    if token is None:
        return None
    headers = {"Authorization": f"Bearer {token.credentials}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://discord.com/api/users/@me", headers=headers
            )
            response.raise_for_status()
            user_data = response.json()
            return int(user_data["id"])
        except Exception:
            return None


class TokenRequest(BaseModel):
    code: str


@app.post("/api/token")
async def exchange_code_for_token(request: TokenRequest):
    log.info(f"[Lobby] Token exchange request")
    client_id = os.getenv("VITE_DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500, detail="Server missing Discord credentials"
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
            return JSONResponse(content=response.json())
        except httpx.HTTPStatusError as e:
            log.error(f"[Lobby] Token exchange failed: {e.response.status_code}")
            raise HTTPException(status_code=500, detail="Token exchange failed")
        except httpx.RequestError as e:
            log.error(f"[Lobby] Network error: {e}")
            raise HTTPException(status_code=503, detail="Service Unavailable")


@app.get("/api/intent")
async def get_user_intent(user_id: str):
    """读取并消费用户意图（一次性）"""
    from src.chat.utils.database import chat_db_manager

    key = f"user_intent:{user_id}"
    value = await chat_db_manager.get_global_setting(key)
    if value:
        await chat_db_manager.delete_global_setting(key)
        log.info(f"[Lobby] Consumed intent for user {user_id}: {value}")
        return JSONResponse(content={"module": value})
    log.info(f"[Lobby] No intent found for user {user_id}")
    return JSONResponse(content={"module": None})


static_files_path = os.path.join(os.path.dirname(__file__), "dist")

if os.path.isdir(static_files_path):
    print(f"[Lobby] Serving static files from: {static_files_path}")
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print("[Lobby] Frontend 'dist' directory not found. Static serving disabled.")
