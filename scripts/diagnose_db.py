import asyncio
import os
import sqlite3
import sys
import logging

# 配置日志记录
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 将项目根目录添加到 sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _PROJECT_ROOT)

from src.chat.utils.database import ChatDatabaseManager


async def main():
    """
    诊断数据库连接和完整性，并尝试复现 a bug。
    """
    log = logging.getLogger(__name__)
    log.info("--- 开始数据库诊断 ---")

    # 1. 打印环境信息
    log.info(f"Python 版本: {sys.version}")
    log.info(f"SQLite3 模块版本: {sqlite3.version}")
    log.info(f"SQLite 库版本: {sqlite3.sqlite_version}")

    db_manager = ChatDatabaseManager()
    test_channel_id = 1234567890  # 使用一个虚拟的频道ID进行测试

    try:
        # 2. 连接数据库
        await db_manager.connect()
        log.info("数据库连接成功。")

        # 3. 检查数据库完整性
        log.info("正在执行 PRAGMA integrity_check...")
        try:
            # integrity_check 需要在一个事务中执行
            check_result = await db_manager._execute(
                db_manager._db_transaction, "PRAGMA integrity_check;", (), fetch="one"
            )
            log.info(f"数据库完整性检查结果: {check_result}")
            if check_result and check_result != "ok":
                log.error(
                    f"数据库完整性检查失败！结果: {check_result}。这可能是问题根源。"
                )
            else:
                log.info("数据库完整性检查通过。")
        except Exception as e:
            log.error(f"执行 integrity_check 时出错: {e}", exc_info=True)

        # 4. 尝试调用一个已知在您本地成功的函数
        log.info(f"正在尝试调用 is_channel_muted(channel_id={test_channel_id})...")
        try:
            is_muted = await db_manager.is_channel_muted(test_channel_id)
            log.info(
                f"is_channel_muted 调用成功。频道 {test_channel_id} 的禁言状态是: {is_muted}"
            )
        except Exception as e:
            log.error(f"调用 is_channel_muted 时捕获到异常: {e}", exc_info=True)

        # 5. 尝试精确复现生产环境中 coin_service 的失败查询
        log.info("--- 开始精确复现生产环境错误 ---")
        # 使用您日志中失败的用户ID
        test_user_id = 1262067786432385164
        failing_query = (
            "SELECT last_daily_message_date FROM user_coins WHERE user_id = ?"
        )
        log.info(f"正在尝试执行查询: '{failing_query}' with user_id: {test_user_id}")
        try:
            result = await db_manager._execute(
                db_manager._db_transaction, failing_query, (test_user_id,), fetch="one"
            )
            log.info(f"生产环境的特定查询成功。结果: {result}")
        except Exception as e:
            log.error(f"执行生产环境的特定查询时捕获到异常: {e}", exc_info=True)
            log.error(
                "!!! 如果此处出现 'bad parameter or other API misuse'，则说明已精确复现生产环境的 bug。"
            )

    except Exception as e:
        log.error(f"诊断脚本执行过程中发生意外错误: {e}", exc_info=True)
    finally:
        if db_manager.conn:
            await db_manager.disconnect()
            log.info("数据库连接已关闭。")
        log.info("--- 数据库诊断结束 ---")


if __name__ == "__main__":
    asyncio.run(main())
