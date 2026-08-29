import logging
from typing import Optional

from fastapi import APIRouter, Depends

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/api/audit")
async def list_audit_entries(
    page: int = 1,
    page_size: int = 50,
    target_type: Optional[str] = None,
):
    return await audit_log_service.list_entries(
        page=page, page_size=page_size, target_type=target_type
    )
