import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# 从根目录加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI()


class TokenRequest(BaseModel):
    code: str


@app.post("/api/token")
async def exchange_code_for_token(request: TokenRequest):
    """API: 用Discord返回的code换取access_token"""
    client_id = os.getenv("VITE_DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")

    if not client_id or not client_secret:
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

    try:
        response = requests.post(
            "https://discord.com/api/oauth2/token", data=data, headers=headers
        )
        response.raise_for_status()
        return JSONResponse(content=response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error exchanging code: {e}")
        print(f"Discord response: {e.response.text if e.response else 'No response'}")
        raise HTTPException(
            status_code=500, detail="Failed to exchange code with Discord"
        )


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
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(static_files_path, "assets")),
        name="assets",
    )

    @app.get("/{catchall:path}")
    async def serve_index(request: Request):
        """为所有其他路由提供 index.html，以支持前端路由"""
        index_path = os.path.join(static_files_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse(
            status_code=404,
            content={"message": "index.html not found in dist directory."},
        )
else:
    print(
        "INFO:     Frontend 'dist' directory not found. Static file serving is disabled."
    )
    print("INFO:     This is normal in development when using the Vite dev server.")


# 运行命令: uvicorn web.app:app --reload --port 8000
