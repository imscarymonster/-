# 路由模块 — RESTful API 接口定义
from fastapi import APIRouter

# 乘客端路由
passenger_router = APIRouter(prefix="/api/v1", tags=["乘客端"])

# 司机端路由
driver_router = APIRouter(prefix="/api/v1", tags=["司机端"])

# 管理员端路由
admin_router = APIRouter(prefix="/api/v1/admin", tags=["管理员端"])

# ==================== 乘客接口 ====================

@passenger_router.get("/routes")
async def get_routes():
    """获取所有线路"""
    return {"routes": []}

@passenger_router.get("/routes/{route_id}/stations")
async def get_stations(route_id: int):
    """获取指定线路的站点列表"""
    return {"stations": []}

@passenger_router.get("/buses/{bus_id}/realtime")
async def get_bus_realtime(bus_id: int):
    """获取车辆实时位置与到站倒计时"""
    return {"bus_id": bus_id, "latitude": 0, "longitude": 0, "eta_seconds": 0}

# ==================== 司机接口 ====================

@driver_router.get("/drivers/{driver_id}/dispatch")
async def get_dispatch(driver_id: int):
    """获取当前司机的调度指令"""
    return {"driver_id": driver_id, "instructions": []}

@driver_router.post("/drivers/{driver_id}/dispatch/{dispatch_id}/accept")
async def accept_dispatch(driver_id: int, dispatch_id: int):
    """司机确认接受调度"""
    return {"status": "accepted"}

# ==================== 管理接口 ====================

@admin_router.get("/heatmap")
async def get_heatmap():
    """获取全网瞬时客流热力分布"""
    return {"heatmap": []}

@admin_router.get("/buses")
async def get_all_buses():
    """获取所有车辆实时状态"""
    return {"buses": []}

@admin_router.get("/stats")
async def get_stats():
    """获取效能统计指标"""
    return {
        "avg_wait_seconds": 0,
        "invalid_mileage_km": 0,
        "total_trips": 0,
    }
