# -*- coding: utf-8 -*-
"""Ollama Embedding 服务类，支持 bge-m3 和 qwen3-embedding 模型生成 embedding"""

import httpx
import logging
from typing import Optional, List, Literal

from src.chat.config.chat_config import OLLAMA_CONFIG, QWEN_EMBEDDING_CONFIG

log = logging.getLogger(__name__)

# 支持的 embedding 模型类型
EmbeddingModelType = Literal["bge", "qwen"]


class OllamaEmbeddingService:
    """Ollama Embedding 服务类，支持 bge-m3 和 qwen3-embedding 模型"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        model_type: EmbeddingModelType = "bge",
    ):
        """
        初始化 Ollama Embedding 服务

        Args:
            base_url: Ollama 服务地址，默认从配置文件读取
            model: 使用的模型名称，默认从配置文件读取
            model_type: 模型类型，"bge" 或 "qwen"，决定使用哪个配置
        """
        self.model_type = model_type
        if model_type == "qwen":
            config = QWEN_EMBEDDING_CONFIG
            self.base_url = base_url or config["BASE_URL"]
            self.model = model or config["MODEL"]
        else:
            self.base_url = base_url or OLLAMA_CONFIG["BASE_URL"]
            self.model = model or OLLAMA_CONFIG["MODEL"]

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
    ) -> Optional[List[float]]:
        """
        使用 Ollama 生成 embedding

        Args:
            text: 要生成 embedding 的文本
            task_type: 任务类型，用于 bge-m3 的指令微调
                       - retrieval_document: 文档检索
                       - retrieval_query: 查询检索
            title: 可选的标题，用于某些模型的特殊处理

        Returns:
            embedding 向量列表，失败时返回 None
        """
        try:
            # 清理文本中的无效 Unicode surrogate 字符
            text = self._clean_text(text)

            # 根据模型类型决定是否添加指令前缀
            # bge-m3 支持指令微调，qwen3-embedding 不需要指令前缀
            prompt = text
            if self.model_type == "bge":
                instruction = ""
                if task_type == "retrieval_query":
                    instruction = "为这个句子生成表示以用于检索相关文章："
                elif task_type == "retrieval_document":
                    instruction = "为这个段落生成表示以用于检索："
                prompt = f"{instruction}{text}" if instruction else text

            # 第一次调用需要加载模型到内存，需要更长的超时时间
            timeout = httpx.Timeout(120.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                url = f"{self.base_url}/api/embeddings"
                log.debug(f"正在请求 Ollama API: {url}, 模型: {self.model}")
                response = await client.post(
                    url,
                    json={"model": self.model, "prompt": prompt},
                )
                response.raise_for_status()
                result = response.json()
                return result.get("embedding")
        except httpx.HTTPStatusError as e:
            log.error(
                f"Ollama API HTTP 错误: {e.response.status_code} - {e.response.text}"
            )
            log.error(f"请求 URL: {self.base_url}/api/embeddings")
            log.error(f"模型: {self.model}")
        except httpx.RequestError as e:
            log.error(f"Ollama API 请求错误: {e}")
            log.error(f"请求 URL: {self.base_url}/api/embeddings")
        except Exception as e:
            log.error(f"生成 embedding 失败: {e}")
        return None

    def _clean_text(self, text: str) -> str:
        """
        清理文本中的无效 Unicode 字符（如 surrogate 字符）

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return text
        # 使用 errors='replace' 编码再解码来处理无效字符
        # 或者使用 surrogatepass 策略来移除 surrogate 字符
        try:
            # 尝试编码为 UTF-8，如果失败则清理
            text.encode("utf-8")
            return text
        except UnicodeEncodeError:
            # 移除 surrogate 字符
            return text.encode("utf-8", errors="ignore").decode("utf-8")

    async def generate_embeddings_batch(
        self, texts: List[str], task_type: str = "retrieval_document"
    ) -> List[Optional[List[float]]]:
        """
        批量生成 embedding（使用 Ollama 的批量 API）

        Args:
            texts: 要生成 embedding 的文本列表
            task_type: 任务类型

        Returns:
            embedding 向量列表
        """
        if not texts:
            return []

        try:
            # 根据模型类型决定是否添加指令前缀
            # bge-m3 支持指令微调，qwen3-embedding 不需要指令前缀
            prompts = texts
            if self.model_type == "bge":
                instruction = ""
                if task_type == "retrieval_query":
                    instruction = "为这个句子生成表示以用于检索相关文章："
                elif task_type == "retrieval_document":
                    instruction = "为这个段落生成表示以用于检索："
                prompts = [
                    f"{instruction}{text}" if instruction else text for text in texts
                ]

            # 使用 Ollama 的批量 API
            timeout = httpx.Timeout(300.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                url = f"{self.base_url}/api/embed"
                log.debug(
                    f"正在请求 Ollama 批量 API: {url}, 模型: {self.model}, 文本数: {len(texts)}"
                )
                response = await client.post(
                    url,
                    json={"model": self.model, "input": prompts},
                )
                response.raise_for_status()
                result = response.json()

                # Ollama 批量 API 返回格式: {"embeddings": [[...], [...], ...]}
                embeddings = result.get("embeddings", [])
                return embeddings
        except httpx.HTTPStatusError as e:
            log.error(
                f"Ollama 批量 API HTTP 错误: {e.response.status_code} - {e.response.text}"
            )
            log.error(f"请求 URL: {self.base_url}/api/embed")
            log.error(f"模型: {self.model}")
        except httpx.RequestError as e:
            log.error(f"Ollama 批量 API 请求错误: {e}")
            log.error(f"请求 URL: {self.base_url}/api/embed")
        except Exception as e:
            log.error(f"批量生成 embedding 失败: {e}")

        # 失败时回退到逐个处理
        log.warning("批量处理失败，回退到逐个处理...")
        results = []
        for text in texts:
            embedding = await self.generate_embedding(text, task_type)
            results.append(embedding)
        return results

    async def check_connection(self) -> bool:
        """
        检查 Ollama 服务是否可用（异步版本）

        Returns:
            服务是否可用
        """
        try:
            timeout = httpx.Timeout(5.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            log.error(f"检查 Ollama 连接失败: {e}")
            return False

    def check_connection_sync(self) -> bool:
        """
        检查 Ollama 服务是否可用（同步版本，用于非异步上下文）

        Returns:
            服务是否可用
        """
        try:
            import requests

            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            log.error(f"检查 Ollama 连接失败: {e}")
            return False


# 全局实例
ollama_embedding_service = OllamaEmbeddingService(model_type="bge")
qwen_embedding_service = OllamaEmbeddingService(model_type="qwen")
