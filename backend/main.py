# OptiBus 后端主入口
# FastAPI 应用启动类

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="OptiBus API",
    description="试验区动态摆渡车优化调度系统",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api import routes

@app.get("/")
async def root():
    return {"message": "OptiBus API is running"}
