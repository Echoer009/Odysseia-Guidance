from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import logging
import os

from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.services.event_service import event_service
import asyncio
from sqlalchemy import text
from src.database.database import AsyncSessionLocal
from src.chat.utils.database import chat_db_manager
from src.chat.features.tutorial_search.services.tutorial_rag_service import (
    tutorial_rag_service,
)

log = logging.getLogger(__name__)


@dataclass
class ShopData:
    """封装商店UI所需的所有数据"""

    balance: int
    items: List[Dict[str, Any]]
    announcement: Optional[str] = None
    active_event: Optional[Dict[str, Any]] = None
    show_tutorial_button: bool = False
    tutorials: List[Dict[str, Any]] = field(default_factory=list)
    thread_id: Optional[int] = None


class ShopService:
    """负责处理与商店相关的数据和业务逻辑"""

    async def prepare_shop_data(self, user_id: int) -> ShopData:
        """
        准备构建商店所需的所有数据。

        Args:
            user_id: 请求商店的用户的ID。

        Returns:
            一个 ShopData 对象，包含了构建UI所需的所有信息。
        """
        try:
            # 1. 获取用户余额和商品列表
            balance = await coin_service.get_balance(user_id)
            items_rows = await coin_service.get_all_items()
            items = [dict(item) for item in items_rows]

            # 2. 处理特定商品的业务逻辑（例如，个人记忆功能）
            user_profile = await chat_db_manager.get_user_profile(user_id)
            has_personal_memory = (
                getattr(user_profile, "has_personal_memory", False)
                if user_profile
                else False
            )
            if has_personal_memory:
                for item in items:
                    if item.get("name") == "个人记忆功能":
                        item["price"] = 10
                        break

            # 3. 获取商店公告
            announcement = self._get_shop_announcement()

            # 4. 获取当前活动
            active_event = event_service.get_active_event()

            # 5. TODO: 在未来的步骤中，这里将添加检查用户是否为帖子作者的逻辑
            show_tutorial_button = False

            return ShopData(
                balance=balance,
                items=items,
                announcement=announcement,
                active_event=active_event,
                show_tutorial_button=show_tutorial_button,
            )
        except Exception as e:
            log.error(f"为用户 {user_id} 准备商店数据时出错: {e}", exc_info=True)
            raise

    def _get_shop_announcement(self) -> Optional[str]:
        """读取商店公告文件内容"""
        try:
            announcement_path = "src/chat/features/odysseia_coin/shop_announcement.md"
            if (
                os.path.exists(announcement_path)
                and os.path.getsize(announcement_path) > 0
            ):
                with open(announcement_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            log.error(f"读取商店公告时出错: {e}")
        return None

    async def get_tutorials_by_author(self, author_id: int) -> List[Dict[str, Any]]:
        """根据作者ID从数据库获取教程列表"""
        query = text("""
            SELECT id, title, created_at
            FROM tutorials.tutorial_documents
            WHERE author_id = :author_id
            ORDER BY created_at DESC;
        """)
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(query, {"author_id": str(author_id)})
                tutorials = result.mappings().all()
                return [dict(row) for row in tutorials]
        except Exception as e:
            log.error(f"为作者 {author_id} 获取教程时出错: {e}", exc_info=True)
            return []

    async def add_tutorial(
        self,
        title: str,
        description: str,
        author_id: int,
        author_name: str,
        thread_id: int,
    ) -> bool:
        """向数据库添加一个新的教程文档，并触发后台RAG处理。"""
        query = text(
            """
            INSERT INTO tutorials.tutorial_documents
            (title, original_content, author_id, author, thread_id)
            VALUES (:title, :description, :author_id, :author_name, :thread_id)
            RETURNING id;
        """
        )
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    query,
                    {
                        "title": title,
                        "description": description,
                        "author_id": str(author_id),
                        "author_name": author_name,
                        "thread_id": str(thread_id),
                    },
                )
                await session.commit()
                new_document_id = result.scalar_one_or_none()

                if new_document_id:
                    log.info(
                        f"教程 '{title}' 已成功添加到数据库，ID: {new_document_id}。准备进行RAG处理。"
                    )
                    asyncio.create_task(
                        tutorial_rag_service.process_tutorial_document(new_document_id)
                    )
                    return True
                else:
                    log.error(f"未能获取新添加教程 '{title}' 的ID。")
                    return False
        except Exception as e:
            log.error(f"添加教程 '{title}' 时出错: {e}", exc_info=True)
            return False

    async def delete_tutorial(self, tutorial_id: int, author_id: int) -> bool:
        """删除一个教程，包括其数据库记录和向量存储。"""
        log.info(f"用户 {author_id} 正在尝试删除教程 ID: {tutorial_id}")
        try:
            async with AsyncSessionLocal.begin() as session:
                log.info(f"正在从向量存储中删除教程 ID: {tutorial_id} 的向量...")
                delete_success = (
                    await tutorial_rag_service.delete_vectors_by_document_id(
                        tutorial_id, session=session
                    )
                )
                if not delete_success:
                    log.error(
                        f"从向量存储中删除教程 ID: {tutorial_id} 失败。正在回滚事务。"
                    )
                    return False
                log.info(f"成功从向量存储中删除教程 ID: {tutorial_id} 的向量。")

                query = text(
                    """
                    DELETE FROM tutorials.tutorial_documents
                    WHERE id = :tutorial_id AND author_id = :author_id
                    RETURNING id;
                """
                )
                result = await session.execute(
                    query,
                    {
                        "tutorial_id": tutorial_id,
                        "author_id": str(author_id),
                    },
                )
                deleted_id = result.scalar_one_or_none()

                if deleted_id is None:
                    log.warning(
                        f"删除教程失败：教程 ID: {tutorial_id} 不存在，或用户 {author_id} 不是作者。正在回滚。"
                    )
                    return False

            log.info(f"已成功从主数据库中删除教程 ID: {deleted_id}。事务已提交。")
            return True

        except Exception as e:
            log.error(
                f"删除教程 ID: {tutorial_id} 的过程中发生意外错误: {e}",
                exc_info=True,
            )
            return False

    async def get_tutorial_by_id(self, tutorial_id: int) -> Dict[str, Any] | None:
        """根据ID获取单个教程的完整内容。"""
        query = text("""
            SELECT id, title, original_content as description
            FROM tutorials.tutorial_documents
            WHERE id = :tutorial_id;
        """)
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(query, {"tutorial_id": tutorial_id})
                tutorial = result.mappings().one_or_none()
                return dict(tutorial) if tutorial else None
        except Exception as e:
            log.error(f"获取教程ID {tutorial_id} 时出错: {e}", exc_info=True)
            return None

    async def update_tutorial(
        self, tutorial_id: int, title: str, description: str, author_id: int
    ) -> bool:
        """更新一个教程，包括其数据库记录和向量存储。"""
        log.info(f"用户 {author_id} 正在尝试更新教程 ID: {tutorial_id}")
        try:
            async with AsyncSessionLocal.begin() as session:
                # 1. 删除旧的向量
                log.info(f"正在为教程更新删除旧向量 (ID: {tutorial_id})...")
                delete_success = (
                    await tutorial_rag_service.delete_vectors_by_document_id(
                        tutorial_id, session=session
                    )
                )
                if not delete_success:
                    log.error(f"为教程 {tutorial_id} 删除旧向量失败。正在回滚。")
                    return False
                log.info(f"成功删除教程 {tutorial_id} 的旧向量。")

                # 2. 更新主数据库中的教程记录
                update_query = text(
                    """
                    UPDATE tutorials.tutorial_documents
                    SET title = :title, original_content = :description, updated_at = NOW()
                    WHERE id = :tutorial_id AND author_id = :author_id
                    RETURNING id;
                """
                )
                result = await session.execute(
                    update_query,
                    {
                        "title": title,
                        "description": description,
                        "tutorial_id": tutorial_id,
                        "author_id": str(author_id),
                    },
                )
                updated_id = result.scalar_one_or_none()

                if updated_id is None:
                    log.warning(
                        f"更新教程失败：教程 ID: {tutorial_id} 不存在，或用户 {author_id} 不是作者。正在回滚。"
                    )
                    return False

            # 事务已提交
            log.info(f"成功在数据库中更新教程 ID: {updated_id}。")

            # 3. 为更新后的内容重新创建向量（在事务外异步执行）
            log.info(f"正在为更新后的教程 {updated_id} 创建后台RAG处理任务...")
            asyncio.create_task(
                tutorial_rag_service.process_tutorial_document(updated_id)
            )
            return True

        except Exception as e:
            log.error(
                f"更新教程 ID: {tutorial_id} 的过程中发生意外错误: {e}",
                exc_info=True,
            )
            return False


shop_service = ShopService()
