# -*- coding: utf-8 -*-

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class UserProgress:
    """代表用户引导进度的业务模型对象。"""

    user_id: int
    guild_id: int
    status: str
    progress_id: Optional[int] = None
    guidance_stage: Optional[str] = None
    selected_tags: List[int] = field(default_factory=list)
    generated_path: List[Dict[str, Any]] = field(default_factory=list)
    completed_path: List[Dict[str, Any]] = field(default_factory=list)
    remaining_path: List[Dict[str, Any]] = field(default_factory=list)
    current_step: Optional[int] = 1

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Optional["UserProgress"]:
        """从数据库行对象创建 UserProgress 实例。"""
        if not row:
            return None

        data = dict(row)
        return cls(
            progress_id=data.get("progress_id"),
            user_id=data["user_id"],
            guild_id=data["guild_id"],
            status=data["status"],
            guidance_stage=data.get("guidance_stage"),
            selected_tags=json.loads(data.get("selected_tags_json") or "[]"),
            generated_path=json.loads(data.get("generated_path_json") or "[]"),
            completed_path=json.loads(data.get("completed_path_json") or "[]"),
            remaining_path=json.loads(data.get("remaining_path_json") or "[]"),
            current_step=data.get("current_step"),
        )

    def to_db_dict(self) -> Dict[str, Any]:
        """将实例转换为可用于数据库更新的字典，并处理JSON序列化。"""
        return {
            "status": self.status,
            "guidance_stage": self.guidance_stage,
            "selected_tags_json": json.dumps(self.selected_tags, ensure_ascii=False),
            "generated_path_json": json.dumps(self.generated_path, ensure_ascii=False),
            "completed_path_json": json.dumps(self.completed_path, ensure_ascii=False),
            "remaining_path_json": json.dumps(self.remaining_path, ensure_ascii=False),
            "current_step": self.current_step,
        }
