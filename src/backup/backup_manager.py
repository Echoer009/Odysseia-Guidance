# -*- coding: utf-8 -*-

import os
import shutil
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# --- 路径配置 ---
# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 源数据目录
DATA_DIR = os.path.join(BASE_DIR, "data")
# 备份目标目录
BACKUP_DIR = os.path.join(BASE_DIR, "src", "backup")
# 数据库文件扩展名
DB_EXTENSIONS = (".db", ".sqlite3")


def backup_databases():
    """
    将所有数据库文件备份到 src/backup 目录，并清理旧备份。
    只保留昨天的备份。
    """
    # 确保备份目录存在
    os.makedirs(BACKUP_DIR, exist_ok=True)

    today = datetime.now()
    yesterday = today - timedelta(days=1)

    # 今天备份文件的日期格式
    backup_date_format = today.strftime("%Y%m%d")
    # 需要保留的备份文件的日期格式
    keep_backup_date_format = yesterday.strftime("%Y%m%d")

    log.info("开始执行数据库备份任务...")

    if not os.path.isdir(DATA_DIR):
        log.warning(f"数据目录 {DATA_DIR} 不存在，跳过备份。")
        return

    # --- 步骤 1: 创建今天的备份 ---
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(DB_EXTENSIONS):
            continue

        source_path = os.path.join(DATA_DIR, filename)
        backup_filename = f"{filename}.bak.{backup_date_format}"
        destination_path = os.path.join(BACKUP_DIR, backup_filename)

        try:
            shutil.copy2(source_path, destination_path)
            log.info(f"成功备份 '{filename}' 到 '{destination_path}'")
        except Exception as e:
            log.error(f"备份 '{filename}' 失败: {e}", exc_info=True)

    # --- 步骤 2: 清理过期的备份 ---
    log.info("开始清理过期备份...")
    for filename in os.listdir(BACKUP_DIR):
        # 备份文件格式为 'chat.db.bak.20251109'
        # 我们要删除所有不包含昨天日期字符串的备份文件
        # 清理逻辑：只保留当天的备份。删除所有文件名不包含今天日期的备份文件。
        if ".bak." in filename and backup_date_format not in filename:
            file_to_delete = os.path.join(BACKUP_DIR, filename)
            try:
                os.remove(file_to_delete)
                log.info(f"已删除过期备份文件: '{filename}'")
            except Exception as e:
                log.error(f"删除过期备份 '{filename}' 失败: {e}", exc_info=True)

    log.info("数据库备份与清理任务完成。")


if __name__ == "__main__":
    # 用于直接运行测试
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    backup_databases()
