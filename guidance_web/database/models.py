# -*- coding: utf-8 -*-
from sqlalchemy.orm import declarative_base

# 定义一个独立的 Base，用于此 guidance 应用的所有模型
Base = declarative_base()

# --- 在这里定义网页引导功能所需的 SQLAlchemy 模型 ---
# 具体的模型字段我们稍后根据需求再来详细设计。
# 例如，我们可能会有一个 WebUserProgress 模型：
#
# class WebUserProgress(Base):
#     __tablename__ = 'web_user_progress'
#     id = Column(Integer, primary_key=True)
#     user_id = Column(BigInteger, nullable=False, index=True)
#     # ... 其他字段 ...
