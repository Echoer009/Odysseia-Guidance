import logging
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.admin import auth
from src.admin.api import (
    ab,
    audit,
    config_api,
    data,
    economy,
    events,
    misc,
    moderation,
    providers_models,
    settings,
    stats,
)
from src.chat.utils.database import chat_db_manager

if not os.getenv("ADMIN_SESSION_SECRET"):
    raise RuntimeError("ADMIN_SESSION_SECRET 未设置，管理后台拒绝启动")

MAX_SAFE_JS_INT = 9007199254740991


def _to_js_safe(value):
    if isinstance(value, dict):
        return {k: _to_js_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_js_safe(v) for v in value]
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and (value > MAX_SAFE_JS_INT or value < -MAX_SAFE_JS_INT)
    ):
        return str(value)
    return value


class BigIntSafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(_to_js_safe(content))


app = FastAPI(
    title="类脑娘 Admin",
    version="1.0.0",
    default_response_class=BigIntSafeJSONResponse,
)
log = logging.getLogger(__name__)


@app.on_event("startup")
async def startup_event():
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s"
    )
    await chat_db_manager.init_async()
    from src.chat.features.tools.tool_loader import load_tools_from_directory

    load_tools_from_directory("src/chat/features/tools/functions")
    log.info("Admin app startup.")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    log.info(f"[Admin] {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        log.info(
            f"[Admin] {request.method} {request.url.path} - {response.status_code}"
        )
        return response
    except Exception as e:
        log.error(f"[Admin] {request.method} {request.url.path} - {e}", exc_info=True)
        raise


app.include_router(auth.router)
app.include_router(settings.router, dependencies=[Depends(auth.require_admin)])
app.include_router(
    providers_models.router, dependencies=[Depends(auth.require_admin)]
)
app.include_router(misc.router, dependencies=[Depends(auth.require_admin)])
app.include_router(ab.router, dependencies=[Depends(auth.require_admin)])
app.include_router(audit.router)
app.include_router(config_api.router)
app.include_router(data.router)
app.include_router(economy.router)
app.include_router(moderation.router)
app.include_router(events.router)
app.include_router(stats.router)

static_files_path = os.path.join(os.path.dirname(__file__), "dist")
index_html_path = os.path.join(static_files_path, "index.html")
# --- 公开法律页面(Discord 应用验证要求公开可访问,免登录) ---
legal_files_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "legal"))
_legal_pages = {
    "terms-of-service": "terms-of-service.html",
    "privacy-policy": "privacy-policy.html",
}


async def _serve_legal_page(page: str, app: str = ""):
    filename = _legal_pages.get(page.removesuffix(".html"))
    if not filename:
        raise HTTPException(status_code=404, detail="Not Found")
    base = os.path.normpath(os.path.join(legal_files_path, app)) if app else legal_files_path
    if not base.startswith(legal_files_path):
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = os.path.normpath(os.path.join(base, filename))
    if not candidate.startswith(base) or not os.path.isfile(candidate):
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(
        candidate,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )


# 同时注册 /legal 与 /admin/legal 两种应用侧路径:
# 反向代理剥离 /admin 前缀时命中前者,原样转发时命中后者。
# /legal/{app}/{page} 服务同域下其他 bot(类脑关注/类脑抽卡)的法律页面。
app.add_api_route(
    "/legal/{page}", _serve_legal_page, methods=["GET", "HEAD"], include_in_schema=False
)
app.add_api_route(
    "/legal/{app}/{page}", _serve_legal_page, methods=["GET", "HEAD"], include_in_schema=False
)
app.add_api_route(
    "/admin/legal/{page}", _serve_legal_page, methods=["GET", "HEAD"], include_in_schema=False
)



@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = os.path.normpath(
        os.path.join(static_files_path, full_path.lstrip("/"))
    )
    if candidate.startswith(static_files_path) and os.path.isfile(candidate):
        return FileResponse(candidate)
    if os.path.isfile(index_html_path):
        if os.path.splitext(full_path)[1]:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(
            index_html_path, headers={"Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="Not Found")

if os.path.isdir(static_files_path):
    print(f"[Admin] Serving static files from: {static_files_path}")
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print("[Admin] Frontend 'dist' directory not found. Static serving disabled.")
    print("[Admin] This is normal in development when using the Vite dev server.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
