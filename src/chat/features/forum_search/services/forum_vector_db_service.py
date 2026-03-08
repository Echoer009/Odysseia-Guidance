# -*- coding: utf-8 -*-

import logging
from typing import List

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

            # 使用 get_or_create_collection 来获取或创建集合，避免每次初始化都删除数据
            # 指定使用余弦距离（适配 bge-m3 模型）
            self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            log.info(
                f"成功连接到论坛搜索 ChromaDB，将操作集合: '{self.collection_name}'（使用余弦距离）"
            )
        except Exception as e:
            log.error(f"初始化论坛搜索 ChromaDB 服务失败: {e}", exc_info=True)
            self.client = None
            self.collection_name = None

    def recreate_collection(self):
        """
        删除并重新创建集合，以确保数据完全同步。
        重写父类方法以使用论坛特定的配置。
        """
        if not self.client or not self.collection_name:
            log.error("论坛 VectorDB 客户端未初始化，无法重新创建集合。")
            return

        try:
            log.info(f"正在删除旧的论坛集合: '{self.collection_name}'...")
            self.client.delete_collection(name=self.collection_name)
            log.info("旧论坛集合已删除。")
        except Exception as e:
            # 即使集合不存在，尝试删除也可能引发异常，但我们可以忽略它
            log.warning(f"删除论坛集合时出现错误 (可能集合不存在，可以忽略): {e}")

        try:
            log.info(f"正在创建新的论坛集合: '{self.collection_name}'...")
            # 创建新集合并指定余弦距离
            self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            log.info("新论坛集合已成功创建。")
        except Exception as e:
            log.error(f"创建新论坛集合时出错: {e}", exc_info=True)

    def get_all_indexed_thread_ids(self) -> List[int]:
        """
        从向量数据库中获取所有已索引的帖子的唯一 thread_id。

        Returns:
            List[int]: 一个包含所有唯一 thread_id 的列表。
        """
        if not self.is_available():
            log.error("向量数据库服务不可用，无法获取已索引的帖子ID。")
            return []

        try:
            # 使用父类的 get 方法获取所有文档的元数据
            results = self.get(include=["metadatas"])

            metadatas = results.get("metadatas")
            if not metadatas:
                return []

            # 从元数据中提取 thread_id 并去重
            thread_ids = []
            seen_ids = set()

            for meta in metadatas:
                if "thread_id" in meta:
                    thread_id = meta["thread_id"]
                    if thread_id not in seen_ids:
                        seen_ids.add(thread_id)
                        thread_ids.append(thread_id)

            return thread_ids
        except Exception as e:
            log.error(f"获取所有已索引的帖子ID时出错: {e}", exc_info=True)
            return []


# 全局实例
forum_vector_db_service = ForumVectorDBService()
