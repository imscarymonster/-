"""FastAPI 应用入口模块。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from . import models
from .database import engine, redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库并检查 Redis 连通性。"""
    models.Base.metadata.create_all(bind=engine)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    redis_client.ping()
    yield


app = FastAPI(title="Optibus Backend", lifespan=lifespan)


@app.get("/")
async def welcome():
    """欢迎接口，确认 FastAPI 服务正常运行。"""
    return {"message": "Welcome to OptiBus backend", "status": "ok"}


@app.get("/health")
async def health():
    """检查 PostgreSQL 和 Redis 的连接状态。"""
    postgres_online = False
    redis_online = False

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        postgres_online = True
    except Exception:
        postgres_online = False

    try:
        redis_online = bool(redis_client.ping())
    except Exception:
        redis_online = False

    return {
        "postgres": "online" if postgres_online else "offline",
        "redis": "online" if redis_online else "offline",
    }


@app.get("/ping")
async def ping():
    return {"message": "pong"}
