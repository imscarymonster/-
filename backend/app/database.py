"""数据库连接配置模块。"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import redis

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/optibus")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

redis_client = redis.Redis.from_url(REDIS_URL)


def get_db():
    """依赖注入：获取 SQLAlchemy 会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
