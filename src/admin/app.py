import logging
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from fastapi import Depends, FastAPI, Request
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

app = FastAPI(title="类脑娘 Admin", version="1.0.0")
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

if os.path.isdir(static_files_path):
    print(f"[Admin] Serving static files from: {static_files_path}")
    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")
else:
    print("[Admin] Frontend 'dist' directory not found. Static serving disabled.")
    print("[Admin] This is normal in development when using the Vite dev server.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
