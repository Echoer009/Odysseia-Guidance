import logging
from typing import Optional

from sqlalchemy import func, select

from src.database.database import AsyncSessionLocal
from src.database.models import AuditLog

log = logging.getLogger(__name__)


class AuditLogService:
    """
    管理后台审计日志服务。
    log 方法保证不抛异常，写入失败仅记录错误日志。
    """

    async def log(
        self,
        user_id: int,
        action: str,
        target_type: str,
        target_id: str = "",
        detail: Optional[dict] = None,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    AuditLog(
                        user_id=user_id,
                        action=action,
                        target_type=target_type,
                        target_id=target_id,
                        detail=detail,
                    )
                )
                await session.commit()
        except Exception as e:
            log.error(
                f"写入审计日志失败 (user={user_id}, action={action}, "
                f"target={target_type}:{target_id}): {e}",
                exc_info=True,
            )

    async def list_entries(
        self,
        page: int = 1,
        page_size: int = 50,
        target_type: Optional[str] = None,
    ) -> dict:
        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        async with AsyncSessionLocal() as session:
            stmt = select(AuditLog)
            count_stmt = select(func.count()).select_from(AuditLog)
            if target_type:
                stmt = stmt.where(AuditLog.target_type == target_type)
                count_stmt = count_stmt.where(AuditLog.target_type == target_type)
            total = await session.scalar(count_stmt) or 0
            result = await session.execute(
                stmt.order_by(AuditLog.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            rows = list(result.scalars().all())
        items = [
            {
                "id": row.id,
                "user_id": row.user_id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "detail": row.detail,
                "created_at": row.created_at.isoformat()
                if row.created_at
                else None,
            }
            for row in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}


audit_log_service = AuditLogService()
