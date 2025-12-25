# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from typing import Optional

from .models import Base  # 假设未来会从 models.py 导入具体的模型


class GuidanceRepository:
    """
    封装所有与网页引导相关的数据库操作。
    这是 Service 层与数据库交互的唯一接口。
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    # --- 在这里定义数据访问方法 ---
    # 稍后我们将根据具体需求来实现这些方法。
    # 例如:
    #
    # async def get_user_progress(self, user_id: int) -> Optional[WebUserProgress]:
    #     return self.db.query(WebUserProgress).filter(WebUserProgress.user_id == user_id).first()
    #
    # async def update_user_progress(self, user_id: int, new_data: dict) -> WebUserProgress:
    #     # ... 更新逻辑 ...
    #     pass
