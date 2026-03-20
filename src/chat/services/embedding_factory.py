# -*- coding: utf-8 -*-
"""
统一的 Embedding 服务工厂

支持三种向量模式:
- "none": 无向量模式，返回 NoneEmbeddingService（所有 embedding 操作返回 None）
- "api": API 向量模式，使用 Gemini Embedding API
- "local": 本地向量模式，使用 Ollama 本地模型

使用方式:
    from src.chat.services.embedding_factory import get_embedding_service

    embedding_service = await get_embedding_service()
    embedding = await embedding_service.generate_embedding("文本内容")
"""

import logging
from typing import Optional, List, Protocol, runtime_checkable
from src.chat.config.chat_config import VECTOR_MODE, VectorMode

log = logging.getLogger(__name__)


@runtime_checkable
class EmbeddingServiceProtocol(Protocol):
    """Embedding 服务协议，定义统一的接口"""

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
    ) -> Optional[List[float]]:
        """生成单个文本的 embedding"""
        ...

    async def check_connection(self) -> bool:
        """检查服务是否可用"""
        ...


class NoneEmbeddingService:
    """无向量模式的服务，所有操作返回 None"""

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
    ) -> Optional[List[float]]:
        """始终返回 None，不生成 embedding"""
        log.debug("[无向量模式] 跳过 embedding 生成")
        return None

    async def check_connection(self) -> bool:
        """无向量模式始终返回 True"""
        return True


class ApiEmbeddingService:
    """API 向量模式的服务，使用 Gemini Embedding API"""

    def __init__(self):
        self._gemini_service = None

    def _get_gemini_service(self):
        """延迟导入 Gemini 服务以避免循环导入"""
        if self._gemini_service is None:
            from src.chat.services.gemini_service import gemini_service

            self._gemini_service = gemini_service
        return self._gemini_service

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
    ) -> Optional[List[float]]:
        """使用 Gemini API 生成 embedding"""
        service = self._get_gemini_service()
        return await service.generate_embedding(text, task_type, title)

    async def check_connection(self) -> bool:
        """检查 Gemini API 是否可用"""
        try:
            service = self._get_gemini_service()
            return service.key_rotation_service is not None
        except Exception:
            return False


class LocalEmbeddingService:
    """本地向量模式的服务，使用 Ollama 本地模型"""

    def __init__(self):
        self._bge_service = None
        self._qwen_service = None
        self._db_manager = None

    def _get_bge_service(self):
        """延迟导入 BGE 服务"""
        if self._bge_service is None:
            from src.chat.services.ollama_embedding_service import (
                ollama_embedding_service,
            )

            self._bge_service = ollama_embedding_service
        return self._bge_service

    def _get_qwen_service(self):
        """延迟导入 Qwen 服务"""
        if self._qwen_service is None:
            from src.chat.services.ollama_embedding_service import (
                qwen_embedding_service,
            )

            self._qwen_service = qwen_embedding_service
        return self._qwen_service

    def _get_db_manager(self):
        """延迟导入数据库管理器"""
        if self._db_manager is None:
            from src.chat.utils.database import chat_db_manager

            self._db_manager = chat_db_manager
        return self._db_manager

    async def _get_current_model(self) -> str:
        """获取当前配置的 embedding 模型"""
        try:
            db_manager = self._get_db_manager()
            model = await db_manager.get_global_setting("embedding_model")
            return model if model else "qwen"  # 默认使用 Qwen
        except Exception:
            return "qwen"

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
    ) -> Optional[List[float]]:
        """使用 Ollama 本地模型生成 embedding"""
        model = await self._get_current_model()
        if model == "qwen":
            service = self._get_qwen_service()
        else:
            service = self._get_bge_service()
        return await service.generate_embedding(text, task_type, title)

    async def check_connection(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            service = self._get_qwen_service()
            return await service.check_connection()
        except Exception:
            return False


# 全局服务实例缓存
_service_cache: dict[VectorMode, EmbeddingServiceProtocol] = {}


def _create_service(mode: VectorMode) -> EmbeddingServiceProtocol:
    """根据模式创建对应的 embedding 服务"""
    if mode == "none":
        return NoneEmbeddingService()
    elif mode == "api":
        return ApiEmbeddingService()
    elif mode == "local":
        return LocalEmbeddingService()
    else:
        log.warning(f"未知的向量模式 '{mode}'，使用本地向量模式")
        return LocalEmbeddingService()


async def get_embedding_service(
    mode: Optional[VectorMode] = None,
) -> EmbeddingServiceProtocol:
    """
    获取 embedding 服务实例

    Args:
        mode: 向量模式，如果为 None 则使用全局配置 VECTOR_MODE

    Returns:
        对应模式的 embedding 服务实例
    """
    use_mode = mode or VECTOR_MODE

    if use_mode not in _service_cache:
        _service_cache[use_mode] = _create_service(use_mode)
        log.info(f"[Embedding 工厂] 创建 {use_mode} 模式的服务实例")

    return _service_cache[use_mode]


def get_embedding_column_for_mode(mode: Optional[VectorMode] = None) -> str:
    """
    根据向量模式返回对应的数据库 embedding 列名

    注意：这个函数是同步的，用于简单场景。
    对于需要动态配置的场景，请使用 async 版本 get_embedding_column()

    Args:
        mode: 向量模式，如果为 None 则使用全局配置 VECTOR_MODE

    Returns:
        embedding 列名，如果模式为 "none" 或 "api" 则返回空字符串
    """
    use_mode = mode or VECTOR_MODE

    if use_mode == "none":
        return ""
    elif use_mode == "api":
        # API 模式暂不支持数据库存储，返回空
        return ""
    elif use_mode == "local":
        # 本地模式默认使用 qwen_embedding
        return "qwen_embedding"
    return "qwen_embedding"


async def get_embedding_column() -> str:
    """
    异步获取当前使用的 embedding 列名

    根据数据库配置返回当前使用的 embedding 列名。
    仅在本地向量模式下有效。

    Returns:
        embedding 列名
    """
    if VECTOR_MODE != "local":
        return ""

    try:
        from src.chat.utils.database import chat_db_manager

        model = await chat_db_manager.get_global_setting("embedding_model")
        return "qwen_embedding" if model == "qwen" else "bge_embedding"
    except Exception:
        return "qwen_embedding"


def is_vector_enabled() -> bool:
    """
    检查是否启用了向量功能

    Returns:
        True 如果向量功能启用（api 或 local 模式），False 如果禁用（none 模式）
    """
    return VECTOR_MODE != "none"


def get_vector_mode() -> VectorMode:
    """
    获取当前配置的向量模式

    Returns:
        当前向量模式
    """
    return VECTOR_MODE
