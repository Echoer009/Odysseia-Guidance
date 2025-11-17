import sqlite3
import os
import argparse
import logging
from pathlib import Path

# 设置日志记录
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def check_database_integrity(db_path: Path) -> bool:
    """
    检查单个 SQLite 数据库文件的完整性。

    Args:
        db_path: 数据库文件的路径。

    Returns:
        True 如果数据库完整性检查通过 ('ok'), 否则 False。
    """
    if not db_path.exists():
        logging.error(f"文件不存在: {db_path}")
        return False

    conn = None
    try:
        logging.info(f"--- 正在检查: {db_path.name} ---")
        # 使用 URI=true 和 mode=ro 以只读模式打开，确保不会修改文件
        # resolve() 会将相对路径转换为绝对路径，以修复 as_uri() 的问题
        db_uri = f"{db_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()

        # 接受纯字符串 'ok' 或元组 ('ok',) 作为检查通过的标志
        if result and (result == "ok" or result == ("ok",)):
            logging.info(f"✅ 完整性检查通过 (OK): {db_path.name}")
            return True
        else:
            logging.error(
                f"❌ 完整性检查失败 (FAILED): {db_path.name} | 返回结果: {result}"
            )
            return False
    except sqlite3.Error as e:
        logging.error(f"❌ 连接或检查数据库时出错: {db_path.name} | 错误: {e}")
        return False
    finally:
        if conn:
            conn.close()
            logging.info(f"--- 检查完成: {db_path.name} ---\n")


def main():
    parser = argparse.ArgumentParser(
        description="批量检查指定文件夹内所有 SQLite (.db) 文件的完整性。"
    )
    parser.add_argument("directory", type=str, help="包含 .db 文件的文件夹路径。")
    args = parser.parse_args()

    target_dir = Path(args.directory)
    if not target_dir.is_dir():
        logging.error(f"错误: 提供的路径不是一个有效的文件夹: {target_dir}")
        return

    logging.info(f"=== 开始扫描文件夹: {target_dir} ===")

    db_files = list(target_dir.glob("*.db"))

    if not db_files:
        logging.warning(f"在文件夹 {target_dir} 中没有找到任何 .db 文件。")
        return

    ok_files = []
    failed_files = []

    for db_file in db_files:
        if check_database_integrity(db_file):
            ok_files.append(db_file.name)
        else:
            failed_files.append(db_file.name)

    logging.info("=== 扫描总结 ===")
    if ok_files:
        logging.info(f"✅ {len(ok_files)} 个文件通过检查: {', '.join(ok_files)}")
    if failed_files:
        logging.error(
            f"❌ {len(failed_files)} 个文件未通过检查: {', '.join(failed_files)}"
        )
    if not ok_files and not failed_files:
        logging.info("没有文件被检查。")


if __name__ == "__main__":
    main()
