"""FastAPI 应用入口模块。"""

from fastapi import FastAPI
from .database import engine, Base

app = FastAPI(title="Optibus Backend")


@app.on_event("startup")
async def on_startup():
    """应用启动时初始化数据库。"""
    Base.metadata.create_all(bind=engine)


@app.get("/")
async def health_check():
    """健康检查接口。"""
    return {"status": "ok", "service": "optibus-backend"}


@app.get("/ping")
async def ping():
    return {"message": "pong"}
