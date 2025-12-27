# -*- coding: utf-8 -*-
import logging

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.database import AsyncSessionLocal
from src.database.models import TutorialDocument, KnowledgeChunk
from src.chat.services.gemini_service import gemini_service
from sqlalchemy.future import select

log = logging.getLogger(__name__)


class TutorialRAGService:
    """
    负责处理作者提交教程后的RAG流程。
    由于Discord模态框的长度限制，每个教程都是一个独立的、
    大小合适的知识单元，因此不再进行文本分割。
    一篇教程（父文档）在向量数据库中对应唯一一个条目（子文档）。
    """

    def __init__(self):
        """初始化服务"""
        log.info("TutorialRAGService 已初始化（简化版，无文本分割）")

    async def process_tutorial_document(self, document_id: int):
        """
        为完整的教程文档内容生成单一向量，并将其作为唯一的块存入数据库。
        """
        log.info(f"开始为文档 ID {document_id} 处理简化的 RAG 流程...")
        try:
            async with AsyncSessionLocal() as session:
                # 1. 查询父文档
                doc_result = await session.execute(
                    select(TutorialDocument).where(TutorialDocument.id == document_id)
                )
                document = doc_result.scalar_one_or_none()

                if not document:
                    log.error(f"无法找到 ID 为 {document_id} 的教程文档。")
                    return

                # 2. 直接使用原始内容作为唯一的 "chunk"
                content = document.original_content
                if not content.strip():
                    log.warning(f"文档 {document_id} 的内容为空。")
                    return

                # 3. 为完整内容生成一个嵌入
                embedding = await gemini_service.generate_embedding(
                    text=content, task_type="retrieval_document"
                )

                if not embedding:
                    log.error(f"为文档 {document_id} 的内容生成嵌入失败。")
                    return

                # 4. 创建并存储唯一的 KnowledgeChunk
                new_chunk = KnowledgeChunk(
                    document_id=document.id,
                    chunk_text=content,  # 存储原文以便可能的调试或预览
                    chunk_order=0,  # 顺序为0，因为只有一个块
                    embedding=embedding,
                )
                session.add(new_chunk)
                await session.commit()
                log.info(f"文档 ID {document_id} 已作为单个单元成功处理并存储。")

        except Exception as e:
            log.error(
                f"处理教程文档 {document_id} 的简化 RAG 流程时发生严重错误: {e}",
                exc_info=True,
            )

    # search 功能将由现有的 tutorial_search_service 统一处理，
    # 以保持查询入口的一致性。该服务仅负责数据的索引。

    async def delete_vectors_by_document_id(
        self, document_id: int, session: AsyncSession
    ) -> bool:
        """
        从 knowledge_chunks 表中删除与特定教程文档关联的所有向量记录。
        这个操作应该在一个更大的事务中被调用。
        """
        log.info(f"准备从数据库中删除文档 ID {document_id} 关联的向量...")
        try:
            # 构建删除语句
            stmt = delete(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document_id
            )
            # 直接在传入的 session 上执行删除操作，以保持事务的原子性
            await session.execute(stmt)
            log.info(f"已成功为文档 ID {document_id} 提交向量删除请求。")
            return True
        except Exception as e:
            log.error(
                f"在删除文档 ID {document_id} 的向量时发生错误: {e}",
                exc_info=True,
            )
            return False


# 创建服务的单例
tutorial_rag_service = TutorialRAGService()
