# -*- coding: utf-8 -*-

"""
存储项目中的非敏感、硬编码的常量。
"""

import os

# --- 路径配置 ---
# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 数据存储目录
DATA_DIR = os.path.join(BASE_DIR, "data")


def _parse_ids(env_var: str) -> set[int]:
    """从环境变量中解析逗号分隔的 ID 列表"""
    ids_str = os.getenv(env_var)
    if not ids_str:
        return set()
    try:
        # 使用集合推导式来解析、转换并去除重复项
        return {int(id_str.strip()) for id_str in ids_str.split(",") if id_str.strip()}
    except ValueError:
        # 如果转换整数失败，返回空集合。在实际应用中，这里可以添加日志记录。
        return set()


# --- 机器人与服务器配置 ---
# 用于在开发时快速同步命令，请在 .env 文件中设置
GUILD_ID = os.getenv("GUILD_ID")

# --- 代理配置 ---
PROXY_URL = os.getenv("PROXY_URL")

# --- Gemini API 配置 ---
# 如果使用自定义的 API 端点（例如通过 Cloudflare Worker 代理），请在此设置
GEMINI_API_BASE_URL = os.getenv("GEMINI_API_BASE_URL")

# --- 权限控制 ---
# 从 .env 文件加载并解析拥有管理权限的用户和角色 ID
DEVELOPER_USER_IDS = _parse_ids("DEVELOPER_USER_IDS")
ADMIN_ROLE_IDS = _parse_ids("ADMIN_ROLE_IDS")

# --- AI 身份配置 ---
# 用于识别AI自身发布的消息，请在 .env 文件中设置
_brain_girl_app_id = os.getenv("BRAIN_GIRL_APP_ID")
BRAIN_GIRL_APP_ID = (
    int(_brain_girl_app_id)
    if _brain_girl_app_id and _brain_girl_app_id.isdigit()
    else None
)

# --- 交互视图相关 ---
VIEW_TIMEOUT = 300  # 交互视图的超时时间（秒），例如按钮、下拉菜单

# --- 日志相关 ---
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(message)s"
LOG_FILE_PATH = os.path.join(DATA_DIR, "bot_debug.log")  # DEBUG 日志文件路径

# --- Embed 颜色 ---
EMBED_COLOR_WELCOME = 0x7289DA  # Discord 官方蓝色
EMBED_COLOR_SUCCESS = 0x57F287  # 绿色
EMBED_COLOR_ERROR = 0xED4245  # 红色
EMBED_COLOR_INFO = 0x3E70DD  # 蓝色
EMBED_COLOR_WARNING = 0xFEE75C  # 黄色
EMBED_COLOR_PURPLE = 0x9B59B6  # 紫色
EMBED_COLOR_PRIMARY = 0x49989A  # 主要 Embed 颜色

# --- RAG 相关配置 ---
# 是否启用RAG查询重写功能 (1 for enabled, 0 for disabled)
RAG_QUERY_REWRITING_ENABLED = int(os.getenv("RAG_QUERY_REWRITING_ENABLED", 1))

# --- 可用 AI 模型 ---
AVAILABLE_AI_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
]
