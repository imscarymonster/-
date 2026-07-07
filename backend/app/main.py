"""FastAPI 应用入口模块。"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from . import models, schemas
from .database import engine, redis_client, Base
from .websocket import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库并检查 Redis 连通性。"""
    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("✅ PostgreSQL 连接成功")
    except Exception:
        print("⚠️ PostgreSQL 连接失败，请检查服务是否启动")

    try:
        redis_client.ping()
        print("✅ Redis 连接成功")
    except Exception:
        print("⚠️ Redis 连接失败，请检查服务是否启动")

    yield


app = FastAPI(title="Optibus Backend", lifespan=lifespan)

# CORS 中间件 —— 便于后续 Vue 前端联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 基础接口 ====================

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


# ==================== 司机端 HTTP 接口 ====================

@app.post("/api/driver/check_in")
async def driver_check_in(data: schemas.DriverDailyCheckIn):
    """司机每日发车打卡。

    将司机初始状态写入 Redis（纯内存操作，不写 PostgreSQL）：
    - Hash  bus:status:all       Field=driver_id, Value=状态 JSON
    - Set   route:buses:{route_id}  记录该线路下的所有车辆
    """
    driver_id = str(data.driver_id)
    initial_status = json.dumps({
        "route_id": data.route_id,
        "lat": 0.0,
        "lng": 0.0,
        "status": "idle",
    })

    # 写入车辆实时状态 Hash
    redis_client.hset("bus:status:all", driver_id, initial_status)

    # 将车辆加入线路车辆集合
    redis_client.sadd(f"route:buses:{data.route_id}", driver_id)

    return {
        "status": "ok",
        "driver_id": data.driver_id,
        "route_id": data.route_id,
    }


# ==================== WebSocket 路由 ====================

@app.websocket("/ws/driver/{driver_id}")
async def driver_websocket(websocket: WebSocket, driver_id: int):
    """司机端 WebSocket 长连接。

    司机连入后持续上报 LocationUpdate 坐标数据；
    每次坐标更新直接覆写 Redis Hash，绝不触碰 PostgreSQL。
    """
    driver_id_str = str(driver_id)
    await manager.connect(websocket, "driver", driver_id_str)

    try:
        while True:
            raw = await websocket.receive_json()

            # 解析并校验坐标数据
            loc = schemas.LocationUpdate(**raw)

            # 读取当前 Redis 中的车辆状态（保留 route_id 等字段）
            current = redis_client.hget("bus:status:all", driver_id_str)
            if current:
                status_data = json.loads(current)
            else:
                # 兜底：如果司机未打卡，用空字段初始化
                status_data = {"route_id": 0, "status": "driving"}

            # 覆写最新经纬度
            status_data["lat"] = loc.lat
            status_data["lng"] = loc.lng
            status_data["status"] = "driving"

            # 写回 Redis Hash（纯内存操作）
            redis_client.hset("bus:status:all", driver_id_str, json.dumps(status_data))

    except WebSocketDisconnect:
        manager.disconnect("driver", driver_id_str)
    except Exception:
        manager.disconnect("driver", driver_id_str)
