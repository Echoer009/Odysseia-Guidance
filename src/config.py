# -*- coding: utf-8 -*-

"""
存储项目中的非敏感、硬编码的常量。
"""

import os

import yaml

# --- 路径配置 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


# --- Bot 身份配置 (从 config/bot.yaml 加载) ---
def _load_bot_identity():
    config_path = os.path.join(BASE_DIR, "config", "bot.yaml")
    if not os.path.exists(config_path):
        return {
            "bot_name": "Bot",
            "community_name": "Community",
            "currency_name": "金币",
            "mascot_title": "看板娘",
            "nickname": "",
            "community_type": "",
            "bot_self_introduction": "",
        }
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("identity", {})


_identity = _load_bot_identity()
BOT_NAME = _identity.get("bot_name", "Bot")
COMMUNITY_NAME = _identity.get("community_name", "Community")
CURRENCY_NAME = _identity.get("currency_name", "金币")
MASCOT_TITLE = _identity.get("mascot_title", "看板娘")
NICKNAME = _identity.get("nickname", "")
COMMUNITY_TYPE = _identity.get("community_type", "")
BOT_SELF_INTRODUCTION = _identity.get("bot_self_introduction", "")


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

# --- 权限控制 ---
# 从 .env 文件加载并解析拥有管理权限的用户和角色 ID
DEVELOPER_USER_IDS = _parse_ids("DEVELOPER_USER_IDS")
ADMIN_ROLE_IDS = _parse_ids("ADMIN_ROLE_IDS")

# --- AI 身份配置 ---
_bot_app_id_str = os.getenv("BOT_APP_ID") or os.getenv("BRAIN_GIRL_APP_ID")
BOT_APP_ID = (
    int(_bot_app_id_str)
    if _bot_app_id_str and _bot_app_id_str.isdigit()
    else None
)
BRAIN_GIRL_APP_ID = BOT_APP_ID

# --- 交互视图相关 ---
VIEW_TIMEOUT = 300  # 交互视图的超时时间（秒），例如按钮、下拉菜单

# --- 日志相关 ---
LOG_LEVEL = "INFO"
# 详细的日志格式，包含时间、级别、模块、函数和行号
LOG_FORMAT = (
    "%(asctime)s - %(levelname)-8s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s"
)
LOG_FILE_PATH = os.path.join(DATA_DIR, "bot_debug.log")  # DEBUG 日志文件路径

# --- Embed 颜色 ---
EMBED_COLOR_WELCOME = 0x7289DA  # Discord 官方蓝色
EMBED_COLOR_SUCCESS = 0x57F287  # 绿色
EMBED_COLOR_ERROR = 0xED4245  # 红色
EMBED_COLOR_INFO = 0x3E70DD  # 蓝色
EMBED_COLOR_WARNING = 0xFEE75C  # 黄色
EMBED_COLOR_PURPLE = 0x9B59B6  # 紫色
EMBED_COLOR_PRIMARY = 0x49989A  # 主要 Embed 颜色


# --- 可用 AI 模型 ---
# 注意: 此配置已废弃，请使用 ai_service.get_available_models() 获取动态模型列表
# AVAILABLE_AI_MODELS = [
#     "gemini-2.5-flash",
#     "gemini-flash-latest",
#     "gemini-2.5-flash-custom",
#     "gemini-3-pro-preview-custom",
#     "gemini-2.5-pro-custom",
#     "gemini-3-flash-custom",
# ]
