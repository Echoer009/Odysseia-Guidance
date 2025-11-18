# -*- coding: utf-8 -*-

"""
独立的日志配置模块。
"""

import logging
import sys
import os
import time
from logging.handlers import RotatingFileHandler
from src import config


def setup_logging():
    """
    配置日志记录器，实现双通道输出：
    - 控制台 (stdout/stderr): 默认只显示 INFO 及以上级别的日志。
    - 日志文件 (bot_debug.log): 记录 DEBUG 及以上级别的所有日志，用于问题排查。
    """
    # 1. 创建一个统一的格式化器
    log_formatter = logging.Formatter(config.LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    # 2. 配置根 logger
    #    为了让文件能记录 DEBUG 信息，根 logger 的级别必须是 DEBUG。
    #    控制台输出的级别将在各自的 handler 中单独控制。
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 设置根 logger 的最低响应级别为 DEBUG
    root_logger.handlers.clear()  # 清除任何可能由其他库（如 discord.py）添加的旧处理器

    # 3. 创建控制台处理器 (stdout)，只显示 INFO 和 DEBUG
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(log_formatter)
    # 从 config 文件读取控制台的日志级别
    console_log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    stdout_handler.setLevel(console_log_level)
    # 添加过滤器，确保 WARNING 及以上级别不会在这里输出
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)

    # 4. 创建控制台处理器 (stderr)，只显示 WARNING 及以上
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(log_formatter)

    # 5. 创建文件处理器，记录所有 DEBUG 及以上级别的日志
    #    使用 RotatingFileHandler 来自动管理日志文件大小
    # 确保日志文件所在的目录存在
    log_dir = os.path.dirname(config.LOG_FILE_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_handler = RotatingFileHandler(
        config.LOG_FILE_PATH,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=2,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录 DEBUG 级别
    file_handler.setFormatter(log_formatter)

    # --- webui ---
    # web_log_formatter = logging.Formatter(
    #     "[%(asctime)s.%(msecs)03dZ] [%(levelname)s] [%(name)s] %(message)s",
    #     datefmt="%Y-%m-%dT%H:%M:%S",
    # )
    # logging.Formatter.converter = time.gmtime

    # 6. 为根 logger 添加所有处理器
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(file_handler)

    # 7. 调整特定库的日志级别，以减少不必要的输出
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
