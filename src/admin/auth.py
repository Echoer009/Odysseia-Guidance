import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from src.config import ADMIN_ROLE_IDS, DEVELOPER_USER_IDS

log = logging.getLogger(__name__)

SESSION_COOKIE = "admin_session"
SESSION_TTL = 7 * 24 * 3600
STATE_TTL = 600

SECRET = os.getenv("ADMIN_SESSION_SECRET")

router = APIRouter()


def _secret() -> str:
    if not SECRET:
        raise RuntimeError("ADMIN_SESSION_SECRET 未设置，管理后台拒绝启动")
    return SECRET


def _sign(payload: str) -> str:
    return hmac.new(
        _secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_session_token(user_id: int) -> str:
    exp = int(time.time()) + SESSION_TTL
    payload = f"{user_id}.{exp}"
    return f"{payload}.{_sign(payload)}"


def verify_session_token(token: str) -> Optional[int]:
    try:
        user_id_str, exp_str, signature = token.rsplit(".", 2)
        payload = f"{user_id_str}.{exp_str}"
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        if int(exp_str) < int(time.time()):
            return None
        return int(user_id_str)
    except (ValueError, AttributeError):
        return None


def create_state() -> str:
    nonce = secrets.token_urlsafe(24)
    exp = int(time.time()) + STATE_TTL
    payload = f"state:{nonce}.{exp}"
    return f"{nonce}.{exp}.{_sign(payload)}"


def verify_state(state: str) -> bool:
    try:
        nonce, exp_str, signature = state.rsplit(".", 2)
        payload = f"state:{nonce}.{exp_str}"
        if not hmac.compare_digest(signature, _sign(payload)):
            return False
        return int(exp_str) >= int(time.time())
    except (ValueError, AttributeError):
        return False


def get_public_base(request: Request) -> str:
    base = os.getenv("ADMIN_PUBLIC_BASE_URL")
    if base:
        return base.rstrip("/")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}/admin"


def _client_id() -> str:
    return (
        os.getenv("ADMIN_DISCORD_CLIENT_ID")
        or os.getenv("DISCORD_CLIENT_ID")
        or os.getenv("VITE_DISCORD_CLIENT_ID")
        or ""
    )


def _primary_guild_id() -> Optional[int]:
    for part in os.getenv("GUILD_ID", "").split(","):
        part = part.strip()
        if part.isdigit():
            return int(part)
    return None


async def require_admin(request: Request) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = verify_session_token(token) if token else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return user_id


async def _has_admin_role(client: httpx.AsyncClient, user_id: int) -> bool:
    if not ADMIN_ROLE_IDS:
        return False
    guild_id = _primary_guild_id()
    bot_token = os.getenv("DISCORD_TOKEN")
    if not guild_id or not bot_token:
        return False
    try:
        response = await client.get(
            f"https://discord.com/api/guilds/{guild_id}/members/{user_id}",
            headers={"Authorization": f"Bot {bot_token}"},
        )
        if response.status_code != 200:
            return False
        roles = {int(r) for r in response.json().get("roles", []) if r.isdigit()}
        return bool(roles & ADMIN_ROLE_IDS)
    except Exception as e:
        log.warning(f"获取用户 {user_id} 的服务器身份组失败: {e}")
        return False


@router.get("/api/auth/login")
async def login(request: Request):
    client_id = _client_id()
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="服务器缺少 Discord OAuth 配置")
    base = get_public_base(request)
    params = {
        "client_id": client_id,
        "redirect_uri": f"{base}/callback",
        "response_type": "code",
        "scope": "identify",
        "state": create_state(),
    }
    url = "https://discord.com/oauth2/authorize?" + urlencode(params)
    return RedirectResponse(url=url, status_code=302)


@router.get("/api/callback")
@router.get("/callback")
async def oauth_callback(
    request: Request, code: Optional[str] = None, state: Optional[str] = None
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="缺少 code 或 state 参数")
    if not verify_state(state):
        raise HTTPException(status_code=400, detail="登录状态校验失败，请重新登录")
    client_id = _client_id()
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="服务器缺少 Discord OAuth 配置")
    base = get_public_base(request)
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"{base}/callback",
    }
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                "https://discord.com/api/oauth2/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=502, detail="Discord 授权失败")
            user_response = await client.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_response.raise_for_status()
            user_id = int(user_response.json()["id"])
            if (
                user_id not in DEVELOPER_USER_IDS
                and not await _has_admin_role(client, user_id)
            ):
                log.warning(f"用户 {user_id} 尝试登录管理后台被拒绝")
                raise HTTPException(status_code=403, detail="您没有管理员权限")
        except httpx.HTTPStatusError as e:
            log.error(f"Discord OAuth 流程失败: {e.response.status_code}", exc_info=True)
            raise HTTPException(status_code=502, detail="Discord 授权失败")
        except httpx.RequestError as e:
            log.error(f"请求 Discord API 时发生网络错误: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail="无法连接 Discord API")
    public_base = os.getenv("ADMIN_PUBLIC_BASE_URL")
    redirect_target = f"{public_base.rstrip('/')}/" if public_base else "/"
    response = RedirectResponse(url=redirect_target, status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        secure=base.startswith("https"),
    )
    return response


@router.get("/api/me")
async def get_me(user_id: int = Depends(require_admin)):
    return {"user_id": user_id}


@router.post("/api/auth/logout")
async def logout(user_id: int = Depends(require_admin)):
    response = JSONResponse(content={"success": True})
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")
    return response
