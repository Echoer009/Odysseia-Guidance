# -*- coding: utf-8 -*-

import logging
import chromadb
from src.chat.config import chat_config as config
from src.chat.services.vector_db_service import VectorDBService

log = logging.getLogger(__name__)


class ForumVectorDBService(VectorDBService):
    """
    专门用于论坛帖子语义搜索的向量数据库服务。
    继承自通用的 VectorDBService，但使用独立的数据库路径和集合。
    """

    def __init__(self):
        try:
            # 使用为论坛搜索定义的特定路径和集合名称
            self.client = chromadb.PersistentClient(path=config.FORUM_VECTOR_DB_PATH)
            self.collection_name = config.FORUM_VECTOR_DB_COLLECTION_NAME

            # 启动时尝试获取或创建一次，以确保数据库连接正常
            self.client.get_or_create_collection(name=self.collection_name)

            log.info(
                f"成功连接到论坛搜索 ChromaDB，将操作集合: '{self.collection_name}'"
            )
        except Exception as e:
            log.error(f"初始化论坛搜索 ChromaDB 服务失败: {e}", exc_info=True)
            self.client = None
            self.collection_name = None


# 全局实例
forum_vector_db_service = ForumVectorDBService()
