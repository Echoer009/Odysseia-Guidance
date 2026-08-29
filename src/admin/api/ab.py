import csv
import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.features.ab_test.services.ab_test_service import ab_test_service

log = logging.getLogger(__name__)
router = APIRouter()

EXPORT_COLUMNS = [
    ("reply_id", "id"),
    ("date", "created_at"),
    ("model", "model_full_id"),
    ("arm_label", "arm_label"),
    ("votes_better", "better"),
    ("votes_worse", "worse"),
    ("votes_same", "same"),
    ("feedback_reasons", "feedback_reasons"),
    ("feedback_texts", "feedback_texts"),
    ("question", "question_text"),
    ("reply", "reply_text"),
]


class ExperimentCreate(BaseModel):
    name: str
    note: Optional[str] = None
    arms: List[Dict[str, Any]]


class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None


class ArmsReplace(BaseModel):
    arms: List[Dict[str, Any]]


class EnabledUpdate(BaseModel):
    enabled: bool


@router.get("/api/ab/experiments")
async def list_experiments():
    return await ab_test_service.list_experiments()


@router.post("/api/ab/experiments")
async def create_experiment(
    body: ExperimentCreate, user_id: int = Depends(require_admin)
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="实验名称不能为空")
    if not body.arms:
        raise HTTPException(status_code=400, detail="至少需要一个实验分组")
    experiment = await ab_test_service.create_experiment(name, body.note, body.arms)
    await audit_log_service.log(
        user_id, "create", "ab_experiment", str(experiment.get("id", "")), {"name": name}
    )
    return experiment


@router.put("/api/ab/experiments/{experiment_id}")
async def update_experiment(
    experiment_id: int, body: ExperimentUpdate, user_id: int = Depends(require_admin)
):
    if body.name is not None and not body.name.strip():
        raise HTTPException(status_code=400, detail="实验名称不能为空")
    experiment = await ab_test_service.update_experiment(
        experiment_id,
        name=body.name.strip() if body.name is not None else None,
        note=body.note,
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="未找到该实验")
    await audit_log_service.log(
        user_id, "update", "ab_experiment", str(experiment_id), {"name": body.name}
    )
    return experiment


@router.put("/api/ab/experiments/{experiment_id}/arms")
async def replace_arms(
    experiment_id: int, body: ArmsReplace, user_id: int = Depends(require_admin)
):
    if not body.arms:
        raise HTTPException(status_code=400, detail="至少需要一个实验分组")
    result = await ab_test_service.replace_arms(experiment_id, body.arms)
    await audit_log_service.log(
        user_id,
        "update",
        "ab_experiment_arms",
        str(experiment_id),
        {"arm_count": len(body.arms)},
    )
    return result


@router.put("/api/ab/experiments/{experiment_id}/enabled")
async def set_experiment_enabled(
    experiment_id: int, body: EnabledUpdate, user_id: int = Depends(require_admin)
):
    await ab_test_service.set_experiment_enabled(experiment_id, body.enabled)
    await audit_log_service.log(
        user_id,
        "update",
        "ab_experiment",
        str(experiment_id),
        {"enabled": body.enabled},
    )
    return {"success": True}


@router.delete("/api/ab/experiments/{experiment_id}")
async def delete_experiment(experiment_id: int, user_id: int = Depends(require_admin)):
    await ab_test_service.delete_experiment(experiment_id)
    await audit_log_service.log(user_id, "delete", "ab_experiment", str(experiment_id))
    return {"success": True}


@router.get("/api/ab/experiments/{experiment_id}/stats")
async def get_experiment_stats(experiment_id: int, days: int = 30):
    days = max(1, min(days, 365))
    return await ab_test_service.get_stats(experiment_id, days)


@router.get("/api/ab/experiments/{experiment_id}/feedback")
async def get_experiment_feedback(experiment_id: int, limit: int = 200):
    limit = max(1, min(limit, 1000))
    return await ab_test_service.list_feedback(experiment_id, limit)


@router.get("/api/ab/experiments/{experiment_id}/export.csv")
async def export_experiment_csv(experiment_id: int, days: int = 30):
    days = max(1, min(days, 365))
    rows = await ab_test_service.export_rows(experiment_id, days)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([column for column, _ in EXPORT_COLUMNS])
    for row in rows:
        cells = []
        for column, field in EXPORT_COLUMNS:
            value = row.get(field, "")
            if column in ("question", "reply") and isinstance(value, str):
                value = value[:500]
            cells.append(value)
        writer.writerow(cells)
    content = "\ufeff" + buffer.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=experiment_{experiment_id}.csv"
        },
    )
