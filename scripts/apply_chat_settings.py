# -*- coding: utf-8 -*-

import json
import asyncio
import os
import sys
import logging

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- 路径设置 ---
# 将项目根目录添加到 sys.path，以便能够导入 src 中的模块
# __file__ 是当前脚本的路径 (e.g., /path/to/project/scripts/apply_chat_settings.py)
# os.path.dirname(__file__) 是脚本所在的目录 (e.g., /path/to/project/scripts)
# os.path.abspath(...) 将其转换为绝对路径
# os.path.join(..., '..') 上移一级到项目根目录
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from src.chat.utils.database import chat_db_manager
except ImportError as e:
    logging.error(
        f"无法导入 'chat_db_manager'。请确保脚本是从项目根目录运行，或者项目结构正确。错误: {e}"
    )
    sys.exit(1)

# --- 常量定义 ---
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "chat_settings_config.json")


async def apply_settings():
    """
    读取配置文件并将其中的聊天设置应用到数据库。
    """
    logging.info("开始应用聊天设置...")

    # 1. 检查并读取配置文件
    if not os.path.exists(CONFIG_FILE_PATH):
        logging.error(f"配置文件未找到: {CONFIG_FILE_PATH}")
        return

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"解析配置文件失败: {e}")
        return
    except Exception as e:
        logging.error(f"读取配置文件时发生未知错误: {e}")
        return

    guild_id = config.get("guild_id")
    settings = config.get("settings")

    if not guild_id or not isinstance(settings, list):
        logging.error("配置文件格式不正确，缺少 'guild_id' 或 'settings' 列表。")
        return

    logging.info(f"成功加载配置，将为服务器 {guild_id} 应用 {len(settings)} 条规则。")

    # 2. 初始化数据库
    # chat_db_manager 是单例，在导入时已初始化，我们只需确保表已创建
    await chat_db_manager.init_async()

    # 3. 遍历并应用设置
    success_count = 0
    for setting in settings:
        entity_id = setting.get("entity_id")
        entity_type = setting.get("entity_type")

        if not entity_id or not entity_type:
            logging.warning(
                f"跳过一条无效的设置记录（缺少 entity_id 或 entity_type）: {setting}"
            )
            continue

        try:
            await chat_db_manager.update_channel_config(
                guild_id=guild_id,
                entity_id=entity_id,
                entity_type=entity_type,
                is_chat_enabled=setting.get("is_chat_enabled"),
                cooldown_seconds=setting.get("cooldown_seconds"),
                cooldown_duration=setting.get("cooldown_duration"),
                cooldown_limit=setting.get("cooldown_limit"),
            )
            logging.info(f"成功应用设置 -> 实体ID: {entity_id} ({entity_type})")
            success_count += 1
        except Exception as e:
            logging.error(
                f"应用设置失败 -> 实体ID: {entity_id} ({entity_type}) | 错误: {e}",
                exc_info=True,
            )

    logging.info("----------------------------------------")
    logging.info(f"所有设置应用完毕。")
    logging.info(f"总规则数: {len(settings)}")
    logging.info(f"成功应用: {success_count}")
    logging.info(f"失败: {len(settings) - success_count}")
    logging.info("----------------------------------------")


if __name__ == "__main__":
    # 使用 asyncio.run() 来执行异步函数
    try:
        asyncio.run(apply_settings())
    except KeyboardInterrupt:
        logging.info("脚本被用户中断。")
