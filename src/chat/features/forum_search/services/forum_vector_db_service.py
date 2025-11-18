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

    def get_all_indexed_thread_ids(self) -> list[int]:
        """
        从向量数据库中获取所有已索引的帖子的唯一 thread_id。

        Returns:
            list[int]: 一个包含所有唯一 thread_id 的列表。
        """
        if not self.is_available():
            log.error("向量数据库服务不可用，无法获取已索引的帖子ID。")
            return []
        try:
            collection = self.client.get_collection(name=self.collection_name)
            # 只获取元数据以提高效率
            results = collection.get(include=["metadatas"])

            if not results or not results["metadatas"]:
                return []

            # 从元数据中提取 thread_id 并去重
            thread_ids = {
                meta["thread_id"]
                for meta in results["metadatas"]
                if "thread_id" in meta
            }
            return list(thread_ids)

        except Exception as e:
            log.error(f"获取所有已索引的帖子ID时出错: {e}", exc_info=True)
            return []


# 全局实例
forum_vector_db_service = ForumVectorDBService()
