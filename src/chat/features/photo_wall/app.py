# -*- coding: utf-8 -*-
"""中秋"大合影"照片墙服务。

运行方式:
    uvicorn src.chat.features.photo_wall.app:app --port 8006

职责:
- Discord OAuth token 交换 + Bearer 鉴权（模式与 blackjack-web 一致）
- 留影条目 CRUD（独立 SQLite: data/photo_wall.db）
- 头像抓取缓存（data/photo_wall/avatars/{user_id}.png）
- 占位背景生成与静态服务（assets/background.jpg，可被手动替换）
- 大合影 PNG 实时合成导出
- 前端静态托管 dist/

关于背景替换: 见 background.py 模块 docstring —— 直接覆盖
src/chat/features/photo_wall/assets/background.jpg 后重启即可。
"""

import asyncio
import json
import logging
import os
import random
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.chat.features.photo_wall.background import generate_background
from src.chat.features.photo_wall.compose import compose_photo
from src.chat.features.photo_wall.db import PhotoWallDB

# --- 路径 ---
BASE_DIR = Path(__file__).resolve().parent          # src/chat/features/photo_wall
REPO_ROOT = BASE_DIR.parents[3]                     # 仓库根目录
DATA_DIR = REPO_ROOT / "data" / "photo_wall"
AVATAR_DIR = DATA_DIR / "avatars"
ASSETS_DIR = BASE_DIR / "assets"
DB_PATH = REPO_ROOT / "data" / "photo_wall.db"
BACKGROUND_PATH = ASSETS_DIR / "background.jpg"

# 从根目录加载 .env 文件
load_dotenv(str(REPO_ROOT / ".env"))

app = FastAPI(title="Mid-Autumn Photo Wall")
log = logging.getLogger(__name__)

photo_wall_db = PhotoWallDB(DB_PATH)

WALL_TITLE = "中秋大合影"

# 画笔禁区布局：管理员涂抹的笔划，涂过的地方禁止放置头像
# strokes = [{"radius": 笔宽(画布宽度比例), "points": [[x比例, y比例], ...]}]
# 存放在源码树 assets 下（data/ 被 gitignore），随仓库一起部署，保存即生效上线
LAYOUT_PATH = ASSETS_DIR / "layout.json"

_BG_CACHE: Dict[str, Any] = {"mtime": None, "size": (4, 3)}


def _background_size() -> Any:
    """读取背景图尺寸（按 mtime 缓存），用于笔划距离的等比换算。"""
    try:
        m = BACKGROUND_PATH.stat().st_mtime
        if _BG_CACHE["mtime"] != m:
            from PIL import Image

            with Image.open(BACKGROUND_PATH) as im:
                _BG_CACHE.update(mtime=m, size=im.size)
    except Exception as e:
        log.warning(f"读取背景尺寸失败: {e}")
    return _BG_CACHE["size"]


def _load_layout() -> List[Dict[str, Any]]:
    """读取画笔禁区笔划列表。"""
    try:
        data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
        strokes = data.get("strokes", [])
        if isinstance(strokes, list):
            out: List[Dict[str, Any]] = []
            for s in strokes:
                if not isinstance(s, dict):
                    continue
                r, pts = s.get("radius"), s.get("points")
                if not isinstance(r, (int, float)) or not isinstance(pts, list) or not pts:
                    continue
                clean = [
                    [float(p[0]), float(p[1])]
                    for p in pts
                    if isinstance(p, (list, tuple)) and len(p) == 2
                ]
                if clean:
                    out.append({"radius": float(r), "points": clean})
            return out
    except FileNotFoundError:
        pass
    except Exception as e:
        log.warning(f"读取画笔禁区失败: {e}")
    return []


def _save_layout(strokes: List[Dict[str, Any]]) -> None:
    LAYOUT_PATH.write_text(
        json.dumps({"strokes": strokes}, ensure_ascii=False), encoding="utf-8"
    )


def _dist_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """点到线段的最短距离。"""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2) ** 0.5


def _avatar_ratio(count: int) -> float:
    """头像直径（相对图片宽度的比例）随人数自适应，与前端/合成器同一梯度。"""
    if count < 20:
        return 0.045
    if count < 50:
        return 0.038
    if count < 100:
        return 0.031
    if count < 200:
        return 0.026
    return 0.022


# 类脑娘口气的提示文案（随机展示，与前端保持同一套语感）
_ZONE_MESSAGES = [
    "这里不可以放哦，会挡住画面里的大家",
    "这片是保留区域呀，换一边试试嘛",
    "这里被涂掉了啦，往旁边挪一挪～",
    "这里圈起来了呀，别处看看吧～",
]

_OVERLAP_MESSAGES = [
    "这里不可以放哦，已经有小伙伴啦",
    "这块地方刚被坐下呀，换个位置嘛",
    "慢了一步，这里有人啦～",
    "挤不下啦，旁边找找看哦",
    "这里已经有小伙伴了哦，再挑挑别处吧",
]


def _placement_allowed(x: float, y: float) -> bool:
    """判断坐标是否允许放置：画笔涂过的地方禁止放置，未涂抹（或无笔划）全图可放。"""
    strokes = _load_layout()
    if not strokes:
        return True
    w, h = _background_size()
    px, py = x * w, y * h
    for s in strokes:
        r = s["radius"] * w
        pts = s["points"]
        if len(pts) == 1:
            cx, cy = pts[0][0] * w, pts[0][1] * h
            if (px - cx) ** 2 + (py - cy) ** 2 <= r * r:
                return False
            continue
        for i in range(len(pts) - 1):
            ax, ay = pts[i][0] * w, pts[i][1] * h
            bx, by = pts[i + 1][0] * w, pts[i + 1][1] * h
            if _dist_to_segment(px, py, ax, ay, bx, by) <= r:
                return False
    return True

# --- 本地预览模式（不影响生产）：PHOTO_DEV_MODE=1 时无 token 的请求使用固定预览用户 ---
PHOTO_DEV_MODE = os.getenv("PHOTO_DEV_MODE") == "1"
PHOTO_DEV_USER = {"id": 999999, "avatar": None, "username": "PreviewUser", "global_name": "预览用户"}

# 管理员 Discord 用户 ID 列表（逗号分隔），可删除任意留影；预览用户默认视为管理员便于本地测试
PHOTO_ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("PHOTO_ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}


def _is_admin(user: Dict[str, Any]) -> bool:
    """判断用户是否为照片墙管理员。"""
    return user["id"] in PHOTO_ADMIN_IDS or (
        PHOTO_DEV_MODE and user["id"] == PHOTO_DEV_USER["id"]
    )

# --- 输入约束 ---
NAME_MIN, NAME_MAX = 1, 20
BLESSING_MIN, BLESSING_MAX = 1, 100
SCALE_MIN, SCALE_MAX = 0.5, 2.0


# --- 应用生命周期事件 ---
@app.on_event("startup")
async def startup_event():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
    log.info("照片墙服务启动: 初始化...")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    await photo_wall_db.initialize()

    if not BACKGROUND_PATH.is_file():
        log.info("未找到背景图，正在生成占位背景 (1920x1080)...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(generate_background, str(BACKGROUND_PATH)))
        log.info("占位背景已生成: %s", BACKGROUND_PATH)
    else:
        log.info("使用已有背景图: %s", BACKGROUND_PATH)


# --- 中间件：请求日志 ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 本地预览（无 Caddy 剥前缀）：把 /photo/api/* 与 /photo/assets/* 重写后交给对应路由
    path = request.scope.get("path", "")
    for prefix in ("/photo/api/", "/photo/assets/"):
        if path.startswith(prefix):
            request.scope["path"] = path[len("/photo"):]
            break
    log.info(f"{request.method} {request.url.path} - start")
    try:
        response = await call_next(request)
        log.info(f"{request.method} {request.url.path} - {response.status_code}")
        return response
    except Exception as e:
        log.error(f"请求处理出错: {request.method} {request.url.path} - {e}", exc_info=True)
        raise


# --- 安全性和依赖 ---
auth_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    token: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> Dict[str, Any]:
    """依赖项：用 Bearer Token 调 Discord API 换取用户 id / avatar hash / 用户名。"""
    if token is None:
        if PHOTO_DEV_MODE:
            return PHOTO_DEV_USER
        raise HTTPException(status_code=401, detail="Missing authentication token")

    headers = {"Authorization": f"Bearer {token.credentials}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://discord.com/api/users/@me", headers=headers
            )
            response.raise_for_status()
            user_data = response.json()
            user = {
                "id": int(user_data["id"]),
                "avatar": user_data.get("avatar"),
                "username": user_data.get("username"),
                "global_name": user_data.get("global_name"),
            }
            log.info("成功识别用户: %s (%s)", user["username"], user["id"])
            return user
        except httpx.HTTPStatusError as e:
            log.error(
                f"从Discord API获取用户信息失败。状态码: {e.response.status_code}，"
                f"响应: {e.response.text}",
            )
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        except httpx.RequestError as e:
            log.error(f"请求Discord API时发生网络错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Service Unavailable: Cannot connect to Discord API",
            )


# --- 序列化 ---
def _entry_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    avatar_url = f"/api/photo/avatar/{d['user_id']}" if d.get("avatar_path") else None
    return {
        "id": d["id"],
        "user_id": str(d["user_id"]),
        "display_name": d["display_name"],
        "blessing": d["blessing"],
        "x_ratio": d["x_ratio"],
        "y_ratio": d["y_ratio"],
        "scale": d["scale"],
        "avatar_url": avatar_url,
        "created_at": d.get("created_at"),
    }


# --- 头像抓取 ---
def _generate_placeholder_avatar(user_id: int) -> str:
    """为预览用户生成一张本地占位头像。"""
    from PIL import Image, ImageDraw

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (128, 128))
    d = ImageDraw.Draw(img)
    for y in range(128):
        t = y / 127
        d.line(
            [(0, y), (127, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip((120, 90, 200), (60, 30, 120))),
        )
    d.ellipse([24, 24, 104, 104], fill=(245, 240, 225))
    dest = AVATAR_DIR / f"{user_id}.png"
    img.save(dest)
    return str(dest)


async def _fetch_and_cache_avatar(user: Dict[str, Any]) -> str:
    """从 Discord CDN 抓当前用户头像并缓存为 data/photo_wall/avatars/{user_id}.png。"""
    user_id = user["id"]

    # 预览模式下不访问 Discord CDN，直接本地生成占位头像（离线可用）
    if PHOTO_DEV_MODE and user_id == PHOTO_DEV_USER["id"]:
        return await asyncio.get_running_loop().run_in_executor(
            None, partial(_generate_placeholder_avatar, user_id)
        )

    if user.get("avatar"):
        url = f"https://cdn.discordapp.com/avatars/{user_id}/{user['avatar']}.png?size=128"
    else:
        index = (user_id >> 22) % 6  # Discord 默认头像索引算法
        url = f"https://cdn.discordapp.com/embed/avatars/{index}.png"

    dest = AVATAR_DIR / f"{user_id}.png"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
    except (httpx.HTTPError, httpx.RequestError) as e:
        log.error(f"下载用户 {user_id} 头像失败: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="无法从 Discord 下载头像，请稍后重试")

    def _write() -> None:
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    await asyncio.get_running_loop().run_in_executor(None, _write)
    return str(dest)


# --- 请求模型 ---
class TokenRequest(BaseModel):
    code: str


class EntryRequest(BaseModel):
    blessing: str
    x_ratio: float
    y_ratio: float


# --- Discord OAuth ---
@app.post("/api/token")
async def exchange_code_for_token(request: TokenRequest):
    """API: 用Discord返回的code换取access_token"""
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
            return JSONResponse(content=response.json())
        except httpx.HTTPStatusError as e:
            log.error(
                f"与Discord API交换代码失败。状态码: {e.response.status_code}，"
                f"响应: {e.response.text}",
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


# --- 照片墙 API ---
@app.get("/api/photo/config")
async def get_photo_config():
    """API: 页面初始配置 + 全部条目（公开）。"""
    # 背景尺寸随图返回，前端据此让画布保持图片比例、完整显示
    bg_w, bg_h = 4, 3
    try:
        from PIL import Image

        with Image.open(BACKGROUND_PATH) as im:
            bg_w, bg_h = im.size
    except Exception as e:
        log.warning(f"读取背景尺寸失败: {e}")

    rows = await photo_wall_db.get_all_entries()
    return JSONResponse(
        content={
            "title": WALL_TITLE,
            "background_url": "/assets/background.jpg",
            "background_width": bg_w,
            "background_height": bg_h,
            "strokes": _load_layout(),
            "entries": [_entry_to_dict(r) for r in rows],
        }
    )


@app.get("/api/photo/entries")
async def get_photo_entries():
    """API: 全部留影条目（公开）。"""
    rows = await photo_wall_db.get_all_entries()
    return JSONResponse(content={"entries": [_entry_to_dict(r) for r in rows]})


@app.post("/api/photo/entries")
async def upsert_photo_entry(
    request: EntryRequest, user: Dict[str, Any] = Depends(get_current_user)
):
    """API: 提交/更新自己的留影（需鉴权，每人一个位置，重复提交覆盖）。

    头像与名字直接取自 Discord 账号，用户只需填写祝福。
    """
    blessing = request.blessing.strip()

    if not (BLESSING_MIN <= len(blessing) <= BLESSING_MAX):
        raise HTTPException(
            status_code=400,
            detail=f"祝福长度需在 {BLESSING_MIN}-{BLESSING_MAX} 字之间",
        )

    x_ratio = min(1.0, max(0.0, request.x_ratio))
    y_ratio = min(1.0, max(0.0, request.y_ratio))

    if not _placement_allowed(x_ratio, y_ratio):
        raise HTTPException(status_code=400, detail=random.choice(_ZONE_MESSAGES))

    # 防重叠：与其他头像保持最小间距（自己已有的留影不算，允许换位置）
    rows = await photo_wall_db.get_all_entries()
    others = [r for r in rows if r["user_id"] != user["id"]]
    if others:
        w, h = _background_size()
        gap = _avatar_ratio(len(others) + 1) * 1.12 * w
        px, py = x_ratio * w, y_ratio * h
        for r in others:
            dx = float(r["x_ratio"]) * w - px
            dy = float(r["y_ratio"]) * h - py
            if dx * dx + dy * dy <= gap * gap:
                raise HTTPException(
                    status_code=400, detail=random.choice(_OVERLAP_MESSAGES)
                )

    # 名字取 Discord 昵称（global_name 优先，回退 username），截断到存储上限
    display_name = (
        user.get("global_name") or user.get("username") or str(user["id"])
    )[:NAME_MAX]
    avatar_path = await _fetch_and_cache_avatar(user)

    row = await photo_wall_db.upsert_entry(
        user_id=user["id"],
        display_name=display_name,
        blessing=blessing,
        x_ratio=x_ratio,
        y_ratio=y_ratio,
        scale=1.0,
        avatar_path=avatar_path,
    )
    log.info(f"用户 {user['id']} 已留影于 ({x_ratio:.2f}, {y_ratio:.2f})")
    return JSONResponse(content={"success": True, "entry": _entry_to_dict(row)})


@app.get("/api/photo/me")
async def get_photo_me(user: Dict[str, Any] = Depends(get_current_user)):
    """API: 当前用户信息（含是否管理员与自己已有的留影）。"""
    row = await photo_wall_db.get_entry(user["id"])
    return JSONResponse(
        content={
            "user_id": str(user["id"]),
            "username": user.get("global_name") or user.get("username"),
            "is_admin": _is_admin(user),
            "entry": _entry_to_dict(row) if row else None,
        }
    )


@app.delete("/api/photo/entries")
async def delete_photo_entry(user: Dict[str, Any] = Depends(get_current_user)):
    """API: 撤下自己的留影（需鉴权）。"""
    deleted = await photo_wall_db.delete_entry(user["id"])
    return JSONResponse(content={"success": True, "deleted": deleted})


@app.get("/api/photo/layout")
async def get_layout():
    """API: 画笔禁区笔划列表（公开，前端用于放置校验与可视化）。"""
    return JSONResponse(content={"strokes": _load_layout()})


@app.put("/api/photo/layout")
async def put_layout(
    body: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)
):
    """API: 保存画笔禁区（仅管理员）。涂过的地方禁止放置头像。"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可编辑禁区")
    raw = body.get("strokes")
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="strokes 必须是笔划数组")
    strokes: List[Dict[str, Any]] = []
    for s in raw:
        if not isinstance(s, dict):
            raise HTTPException(status_code=400, detail="笔划格式错误")
        r_val = s.get("radius")
        if not isinstance(r_val, (int, float)):
            raise HTTPException(status_code=400, detail="笔宽格式错误")
        radius = float(r_val)
        if not (0.002 <= radius <= 0.2):
            raise HTTPException(status_code=400, detail="笔宽需在 0.002-0.2 之间")
        pts_raw = s.get("points")
        if not isinstance(pts_raw, list) or not pts_raw:
            raise HTTPException(status_code=400, detail="笔划至少需要一个点")
        points = []
        for p in pts_raw:
            try:
                x, y = float(p[0]), float(p[1])
            except (TypeError, ValueError, IndexError):
                raise HTTPException(status_code=400, detail="坐标格式错误")
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise HTTPException(status_code=400, detail="坐标需在 0-1 之间")
            points.append([x, y])
        strokes.append({"radius": radius, "points": points})
    _save_layout(strokes)
    log.info(f"管理员 {user['id']} 更新了画笔禁区：{len(strokes)} 笔")
    return JSONResponse(content={"success": True, "strokes": len(strokes)})


@app.delete("/api/photo/entries/{entry_id}")
async def delete_photo_entry_by_id(
    entry_id: int, user: Dict[str, Any] = Depends(get_current_user)
):
    """API: 管理员删除任意留影（用于清理不合规内容）。"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可删除他人留影")
    deleted = await photo_wall_db.delete_entry_by_id(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="留影不存在或已删除")
    log.info(f"管理员 {user['id']} 删除了留影 {entry_id}")
    return JSONResponse(content={"success": True, "deleted": deleted})


@app.get("/api/photo/avatar/{user_id}")
async def get_photo_avatar(user_id: int):
    """API: 提供缓存的用户头像（公开）。"""
    path = AVATAR_DIR / f"{user_id}.png"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/photo/export")
async def export_photo():
    """API: 实时合成大合影 PNG（公开，供分享/存档）。"""
    rows: List[Any] = await photo_wall_db.get_all_entries()
    entries = [dict(r) for r in rows]
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        None, partial(compose_photo, str(BACKGROUND_PATH), entries)
    )
    return Response(
        content=data,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="photo_wall_export.png"'},
    )


# --- 背景静态服务 ---
@app.get("/assets/background.jpg")
async def get_background():
    """背景图（公开）。替换方式见 background.py docstring。"""
    if not BACKGROUND_PATH.is_file():
        raise HTTPException(status_code=404, detail="Background not ready")
    return FileResponse(BACKGROUND_PATH, media_type="image/jpeg")


# --- 静态文件服务 (仅在生产构建后生效) ---
static_files_path = os.path.join(os.path.dirname(__file__), "dist")

if os.path.isdir(static_files_path):
    print(f"Serving static files from: {static_files_path}")
    # /photo 前缀挂载用于本地预览（前端 base 为 /photo/）
    app.mount("/photo", StaticFiles(directory=static_files_path, html=True), name="static_photo")
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print(
        "INFO:     Frontend 'dist' directory not found. Static file serving is disabled."
    )
    print("INFO:     This is normal in development when using the Vite dev server.")


# 运行命令: uvicorn src.chat.features.photo_wall.app:app --port 8006
