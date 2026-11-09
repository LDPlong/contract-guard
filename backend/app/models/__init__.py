"""ORM 模型注册入口。

新增模型文件后必须在此 import，否则 init_models() 不会建表。
"""

from app.models.base import Base, SessionLocal, engine, get_session
from app.models.document import Clause, Document

__all__ = ["Base", "Clause", "Document", "SessionLocal", "engine", "get_session"]
