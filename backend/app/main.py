"""FastAPI 应用入口模块。"""

import asyncio
import json
import math
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from . import models, schemas
from .database import engine, redis_client, Base
from .websocket import manager

# ============================================================================
# ETA 算法全局常量
# ============================================================================

BUS_SPEED = 8.0                # 大巴速度 (m/s)
STATION_THRESHOLD = 20.0       # 到站判定距离 (m)

# ---------------------------------------------------------------------------
# 1. 核心坐标库 (单位: 米)
# ---------------------------------------------------------------------------
STATIONS_XY: dict[str, tuple[float, float]] = {
    "中传专享楼": (0, 0), "公共教学楼": (186, 140), "公共实验楼": (338, 296),
    "北体专享楼": (418, 444), "综合体育中心游泳馆": (591, 636), "大学生活动中心": (624, 693),
    "会堂": (-54, -300), "双创中心": (-228, -516), "生活一区食堂": (107, -509),
    "生活一区2号门": (77, -260), "生活二区2号门": (287, -78), "1号食堂": (599, 304),
    "自强路站": (811, 616), "北邮专享楼": (-924, -455), "电科专享楼": (-588, -257),
    "体育场": (-195, 67), "图书馆": (-11, 253), "民大专享楼": (236, 531),
    "黎安书院": (294, 620), "立德路站": (312, -334),
    "拐点1": (-147, -189), "拐点2": (-22, -353), "拐点3": (176, -178),
    "拐点5": (639, 731), "拐点6": (449, 857), "拐点7": (-116, 129),
}

# ---------------------------------------------------------------------------
# 2. 线路行进展开数组 (含死胡同折返，索引顺序即真实行驶轨迹)
# ---------------------------------------------------------------------------
ROUTES_SEQUENCE: dict[str, list[str]] = {
    "line2_cw": [
        "中传专享楼", "拐点7", "体育场", "电科专享楼", "北邮专享楼",
        "电科专享楼", "体育场", "拐点7", "图书馆", "民大专享楼",
        "黎安书院", "拐点6", "拐点5", "大学生活动中心", "综合体育中心游泳馆",
        "北体专享楼", "公共实验楼", "公共教学楼", "中传专享楼",
    ],
    "line2_ccw": [],
    "line1_cw": [
        "中传专享楼", "拐点3", "生活二区2号门", "生活一区2号门",
        "拐点1", "会堂", "双创中心",
        "会堂", "拐点1", "拐点2", "生活一区食堂",
        "拐点2", "拐点1", "拐点3", "中传专享楼",
    ],
    "line1_ccw": [],
    "teacher_cw": [
        "中传专享楼", "公共教学楼", "公共实验楼", "公共教学楼",
        "中传专享楼", "拐点3", "立德路站", "拐点3", "中传专享楼",
    ],
    "teacher_ccw": [],
}

ROUTES_SEQUENCE["line2_ccw"] = list(reversed(ROUTES_SEQUENCE["line2_cw"]))
ROUTES_SEQUENCE["line1_ccw"] = list(reversed(ROUTES_SEQUENCE["line1_cw"]))
ROUTES_SEQUENCE["teacher_ccw"] = list(reversed(ROUTES_SEQUENCE["teacher_cw"]))

# ---------------------------------------------------------------------------
# 2b. 纯净路线数组（过滤所有拐点，仅保留真实站点）
# ---------------------------------------------------------------------------
REAL_ROUTES: dict[str, list[str]] = {
    rk: [s for s in seq if "拐点" not in s]
    for rk, seq in ROUTES_SEQUENCE.items()
}

# ---------------------------------------------------------------------------
# 3. 公交编队
# ---------------------------------------------------------------------------
BUS_FLEET: list[dict] = [
    {"busId": "101", "route_key": "line1_cw",   "departure_offset_s": 0},
    {"busId": "102", "route_key": "line1_ccw",  "departure_offset_s": 0},
    {"busId": "103", "route_key": "line2_cw",   "departure_offset_s": 0},
    {"busId": "104", "route_key": "line2_ccw",  "departure_offset_s": 0},
    {"busId": "105", "route_key": "teacher_cw", "departure_offset_s": 0},
    {"busId": "106", "route_key": "teacher_ccw","departure_offset_s": 0},
    {"busId": "107", "route_key": "line1_cw",   "departure_offset_s": 180},
    {"busId": "108", "route_key": "line1_ccw",  "departure_offset_s": 180},
    {"busId": "109", "route_key": "line2_cw",   "departure_offset_s": 180},
    {"busId": "110", "route_key": "line2_ccw",  "departure_offset_s": 180},
]

ALL_ROUTE_KEYS = list(ROUTES_SEQUENCE.keys())

# 仿真起始时间戳（lifespan 中赋值）
_sim_t0: float | None = None

# ============================================================================
# 调度引擎常量
# ============================================================================

BUS_CAPACITY = 13             # 单车标准运力评估值
SAFETY_MARGIN = 5             # 安全余量
DISPATCH_SCAN_INTERVAL = 30   # 后台扫描间隔 (秒)
SIMULATION_SPEEDUP = 5.0      # 演示加速倍率（5x：现实3s=系统15s=1tick）
LIFECYCLE_KEY_PREFIX = "user:lifecycle:"

# 路线单圈耗时缓存
_route_circle_times: dict[str, float] = {}


# ============================================================================
# ETA 核心算法
# ============================================================================

def get_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def point_to_segment_projection(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float,
) -> tuple[float, float, float, float]:
    abx, aby = x2 - x1, y2 - y1
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0:
        dist = math.hypot(px - x1, py - y1)
        return (x1, y1, dist, 0.0)
    t = max(0.0, min(1.0, ((px - x1) * abx + (py - y1) * aby) / ab_len_sq))
    proj_x = x1 + t * abx
    proj_y = y1 + t * aby
    dist_to_seg = math.hypot(px - proj_x, py - proj_y)
    dist_to_b = math.hypot(x2 - proj_x, y2 - proj_y)
    return (proj_x, proj_y, dist_to_seg, dist_to_b)


def snap_vehicle(x: float, y: float, route_key: str) -> tuple[int, float, float]:
    route = ROUTES_SEQUENCE[route_key]
    best_idx, best_dist, best_to_end = 0, float("inf"), 0.0
    for i in range(len(route) - 1):
        x1, y1 = STATIONS_XY[route[i]]
        x2, y2 = STATIONS_XY[route[i + 1]]
        _, _, d_seg, d_to_end = point_to_segment_projection(x, y, x1, y1, x2, y2)
        if d_seg < best_dist:
            best_dist = d_seg
            best_idx = i
            best_to_end = d_to_end
    return best_idx, best_dist, best_to_end


def calculate_eta(
    x: float, y: float, route_key: str, target_station: str,
) -> int | None:
    route = ROUTES_SEQUENCE[route_key]
    if target_station not in route:
        return None
    tx, ty = STATIONS_XY[target_station]
    if get_distance((x, y), (tx, ty)) < STATION_THRESHOLD:
        return 0
    seg_idx, _, dist_to_end = snap_vehicle(x, y, route_key)
    best_eta = float("inf")
    n = len(route)
    for offset in range(n):
        idx = (seg_idx + 1 + offset) % n
        if route[idx] == target_station:
            total = dist_to_end
            cursor = seg_idx + 1
            while cursor % n != idx:
                a = STATIONS_XY[route[cursor % n]]
                b = STATIONS_XY[route[(cursor + 1) % n]]
                total += get_distance(a, b)
                cursor += 1
            eta_min = math.ceil(total / BUS_SPEED / 60)
            if eta_min < best_eta:
                best_eta = eta_min
    return int(best_eta) if best_eta != float("inf") else None


# ============================================================================
# 发车模拟器
# ============================================================================

def get_simulated_position(bus: dict, elapsed_s: float) -> tuple[float, float] | None:
    route = ROUTES_SEQUENCE[bus["route_key"]]
    if len(route) < 2:
        return None
    travel_time = max(0.0, elapsed_s - bus["departure_offset_s"])
    distance_traveled = travel_time * BUS_SPEED
    total_route_len = 0.0
    seg_lengths = []
    for i in range(len(route) - 1):
        d = get_distance(STATIONS_XY[route[i]], STATIONS_XY[route[i + 1]])
        seg_lengths.append(d)
        total_route_len += d
    if total_route_len == 0:
        return STATIONS_XY[route[0]]
    distance_traveled %= total_route_len
    cumulative = 0.0
    for i, seg_len in enumerate(seg_lengths):
        if cumulative + seg_len >= distance_traveled:
            fraction = (distance_traveled - cumulative) / seg_len
            x1, y1 = STATIONS_XY[route[i]]
            x2, y2 = STATIONS_XY[route[i + 1]]
            return (x1 + fraction * (x2 - x1), y1 + fraction * (y2 - y1))
        cumulative += seg_len
    return STATIONS_XY[route[-1]]


def get_simulated_segment_info(
    bus: dict, elapsed_s: float,
) -> tuple[str, str, float, str] | None:
    """纯逻辑拓扑跳跃 —— 基于 15s/tick 滴答器，零物理坐标依赖。

    偶数 tick = 靠站 (arrived, progress=1.0)
    奇数 tick = 行驶中 (in-transit, progress=0.5)

    Returns:
        (fromStation, toStation, progress, status) 或 None
    """
    TICK_S = 15  # 每个逻辑动作 15 秒（停站 / 行驶）

    pure_route = REAL_ROUTES.get(bus["route_key"])
    if not pure_route or len(pure_route) < 2:
        return None

    travel_t = max(0.0, elapsed_s - bus["departure_offset_s"])
    ticks = int(travel_t / TICK_S)
    cycle_len = len(pure_route)

    idx = (ticks // 2) % cycle_len
    next_idx = (idx + 1) % cycle_len

    if ticks % 2 == 0:
        # 偶数 tick：靠站
        return (pure_route[idx], pure_route[next_idx], 1.0, "arrived")
    else:
        # 奇数 tick：两站之间行驶
        return (pure_route[idx], pure_route[next_idx], 0.5, "in-transit")


def build_station_route_map() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for rk, seq in ROUTES_SEQUENCE.items():
        for name in seq:
            if name not in mapping:
                mapping[name] = []
            if rk not in mapping[name]:
                mapping[name].append(rk)
    return mapping


# ============================================================================
# 拓扑段位工具 — 拐点过滤
# ============================================================================

def _is_waypoint(name: str) -> bool:
    """判断站点名是否为拐点（前端不可见）。"""
    return "拐点" in name


def _prev_real_station(route: list[str], seg_idx: int) -> str:
    """从 seg_idx 往前查找第一个真实站点。"""
    for i in range(seg_idx, -1, -1):
        if not _is_waypoint(route[i]):
            return route[i]
    return route[0]


def _next_real_station(route: list[str], seg_idx: int) -> str:
    """从 seg_idx+1 往后查找第一个真实站点。"""
    n = len(route)
    for i in range(seg_idx + 1, n):
        if not _is_waypoint(route[i]):
            return route[i]
    return route[-1]


# ============================================================================
# 调度引擎 — 工具函数
# ============================================================================

def get_route_circle_time(route_key: str) -> float:
    """计算路线单圈总耗时 (秒)。"""
    if route_key in _route_circle_times:
        return _route_circle_times[route_key]
    route = ROUTES_SEQUENCE[route_key]
    total = 0.0
    for i in range(len(route) - 1):
        total += get_distance(STATIONS_XY[route[i]], STATIONS_XY[route[i + 1]])
    ct = total / BUS_SPEED
    _route_circle_times[route_key] = ct
    return ct


def _health_count(bus_count: int) -> float:
    """拥挤度安全线：bus_count * 13 - 5。"""
    return bus_count * BUS_CAPACITY - SAFETY_MARGIN


def _get_bus_count(route_key: str) -> int:
    """读取 Redis 中某线路当前在线车辆数。"""
    raw = redis_client.hget("route:bus_count", route_key)
    return int(raw) if raw else 0


def _get_user_count(route_key: str) -> int:
    """读取 Redis 中某线路当前排队人数。"""
    raw = redis_client.hget("route:user_count", route_key)
    return int(raw) if raw else 0


def _get_fixed_bus_count(route_key: str) -> int:
    """读取某线路原始固定配车数。"""
    raw = redis_client.hget("route:fixed_bus_count", route_key)
    return int(raw) if raw else 0


def _get_bus_current_route_key(bus_data: dict) -> str | None:
    """从 bus:status:all 的单条 JSON 中提取当前 route_key。"""
    return bus_data.get("route_key") or bus_data.get("current_route_key")


def _is_overcrowded(route_key: str) -> bool:
    """目标线是否触发调度：人数 > 安全线。"""
    return _get_user_count(route_key) > _health_count(_get_bus_count(route_key))


def _can_spare_bus(route_key: str) -> bool:
    """闲线抽走一辆后是否仍满足自身安全。"""
    bus_cnt = _get_bus_count(route_key)
    if bus_cnt <= 1:
        return False
    return _health_count(bus_cnt - 1) >= _get_user_count(route_key)


# ============================================================================
# 调度引擎 — 车辆位置查找
# ============================================================================

def _get_real_bus_positions() -> dict[str, tuple[float, float, str | None, dict]]:
    """从 Redis bus:status:all 读取所有真车位置。

    Returns: {busId: (lat, lng, route_key, full_data)}
    """
    result: dict[str, tuple[float, float, str | None, dict]] = {}
    all_buses = redis_client.hgetall("bus:status:all")
    for bus_id, raw_json in all_buses.items():
        try:
            data = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            continue
        lat = data.get("lat", 0.0)
        lng = data.get("lng", 0.0)
        rk = _get_bus_current_route_key(data)
        result[bus_id] = (lat, lng, rk, data)
    return result


def _find_nearest_bus_on_route(
    source_route_key: str, target_route_key: str,
) -> str | None:
    """在 source 线路上找到离 target 线路起点最近的一辆车，返回 busId。"""
    # 目标线路参考点：取第一个站点坐标
    target_route = ROUTES_SEQUENCE[target_route_key]
    target_xy = STATIONS_XY[target_route[0]]

    best_bus_id: str | None = None
    best_dist = float("inf")

    # 真车
    for bus_id, (lat, lng, rk, data) in _get_real_bus_positions().items():
        effective_rk = rk
        if effective_rk is None:
            continue
        if effective_rk != source_route_key:
            continue
        # 跳过已被标记 pending_return 或即将离开的车
        if data.get("pending_return"):
            continue
        d = get_distance((lat, lng), target_xy)
        if d < best_dist:
            best_dist = d
            best_bus_id = bus_id

    # 仿真车（无真车时）
    if best_bus_id is None and _sim_t0 is not None:
        elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
        for b in BUS_FLEET:
            if b["route_key"] != source_route_key:
                continue
            pos = get_simulated_position(b, elapsed)
            if pos is None:
                continue
            d = get_distance(pos, target_xy)
            if d < best_dist:
                best_dist = d
                best_bus_id = b["busId"]

    return best_bus_id


# ============================================================================
# 调度引擎 — 原子变线
# ============================================================================

def _execute_dispatch(target_route_key: str, source_route_key: str) -> bool:
    """从闲线抽调一辆最近的车到目标线。原子操作。返回是否成功。"""
    bus_id = _find_nearest_bus_on_route(source_route_key, target_route_key)
    if bus_id is None:
        return False

    # 读取并更新 bus:status:all
    raw = redis_client.hget("bus:status:all", bus_id)
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    # 记录老东家（若之前未被调度过）
    if "original_route_key" not in data or not data.get("original_route_key"):
        data["original_route_key"] = source_route_key

    data["route_key"] = target_route_key
    data["current_route_key"] = target_route_key
    data["pending_return"] = False
    data["status"] = "dispatched"
    redis_client.hset("bus:status:all", bus_id, json.dumps(data))

    # 原子基数同步
    redis_client.hincrby("route:bus_count", source_route_key, -1)
    redis_client.hincrby("route:bus_count", target_route_key, 1)

    # 防止负数
    src_cnt = int(redis_client.hget("route:bus_count", source_route_key) or 0)
    if src_cnt < 0:
        redis_client.hset("route:bus_count", source_route_key, "0")

    print(f"🚛 调度: {bus_id} 从 {source_route_key} → {target_route_key}")
    return True


# ============================================================================
# 调度引擎 — 脱离调度 (Return)
# ============================================================================

def _execute_return(bus_id: str, data: dict):
    """将一台被调度车归还其原始线路。"""
    original = data.get("original_route_key")
    current = data.get("route_key") or data.get("current_route_key")
    if not original or not current:
        return

    # 恢复 route_key
    data["route_key"] = original
    data["current_route_key"] = original
    data.pop("original_route_key", None)
    data.pop("pending_return", None)
    data["status"] = "driving"
    redis_client.hset("bus:status:all", bus_id, json.dumps(data))

    # 基数同步
    redis_client.hincrby("route:bus_count", current, -1)
    redis_client.hincrby("route:bus_count", original, 1)

    # 防负数
    for rk in (current, original):
        cnt = int(redis_client.hget("route:bus_count", rk) or 0)
        if cnt < 0:
            redis_client.hset("route:bus_count", rk, "0")

    print(f"🏠 归还: {bus_id} 从 {current} → 原线路 {original}")


# ============================================================================
# 调度引擎 — 乘客生命周期清理
# ============================================================================

def _evict_expired_passengers():
    """扫描所有乘客 lifecycle 记录，静默清理超时用户。"""
    now = time.time()
    evicted = 0

    for key in redis_client.scan_iter(f"{LIFECYCLE_KEY_PREFIX}*"):
        raw = redis_client.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            redis_client.delete(key)
            continue

        join_time = data.get("join_time", 0)
        route_key = data.get("route_key", "")
        station_id = data.get("station_id", "")

        if not route_key or route_key not in ROUTES_SEQUENCE:
            redis_client.delete(key)
            continue

        elapsed = now - join_time

        # 计算 ETA：取该线路上任意车辆到乘客站点的最小 ETA
        eta_seconds = 0
        if station_id and station_id in STATIONS_XY:
            min_eta = _get_min_eta_for_station(route_key, station_id)
            eta_seconds = max(0, min_eta) * 60

        circle_time = get_route_circle_time(route_key)
        retention = eta_seconds + circle_time

        if elapsed >= retention:
            redis_client.delete(key)
            redis_client.hincrby("route:user_count", route_key, -1)
            # 防负数
            cnt = int(redis_client.hget("route:user_count", route_key) or 0)
            if cnt < 0:
                redis_client.hset("route:user_count", route_key, "0")
            evicted += 1

    if evicted:
        print(f"🧹 清理过期乘客: {evicted} 人")


def _get_min_eta_for_station(route_key: str, station_id: str) -> int:
    """获取指定线路上最快车辆到某站的 ETA 分钟数。"""
    best = 999
    # 真车
    for _bus_id, (lat, lng, rk, data) in _get_real_bus_positions().items():
        if rk == route_key and not data.get("pending_return"):
            eta = calculate_eta(lat, lng, route_key, station_id)
            if eta is not None and eta < best:
                best = eta
    # 仿真
    if best == 999 and _sim_t0 is not None:
        elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
        for b in BUS_FLEET:
            if b["route_key"] != route_key:
                continue
            pos = get_simulated_position(b, elapsed)
            if pos:
                eta = calculate_eta(pos[0], pos[1], route_key, station_id)
                if eta is not None and eta < best:
                    best = eta
    return best if best != 999 else 0


# ============================================================================
# 调度引擎 — 派单扫描 & 归还扫描
# ============================================================================

def _check_all_dispatch_conditions():
    """遍历所有线路，触发运力抽调。"""
    for target_rk in ALL_ROUTE_KEYS:
        if not _is_overcrowded(target_rk):
            continue

        # 寻找可抽调的闲线
        candidates = [rk for rk in ALL_ROUTE_KEYS if rk != target_rk and _can_spare_bus(rk)]
        if not candidates:
            continue

        # 按到目标线的物理距离排序闲线（用各闲线第一站坐标）
        target_xy = STATIONS_XY[ROUTES_SEQUENCE[target_rk][0]]
        candidates.sort(key=lambda rk: get_distance(
            STATIONS_XY[ROUTES_SEQUENCE[rk][0]], target_xy))

        # 逐辆抽调，直到目标线恢复健康
        for src_rk in candidates:
            if not _is_overcrowded(target_rk):
                break
            if not _can_spare_bus(src_rk):
                continue
            _execute_dispatch(target_rk, src_rk)


def _check_all_return_conditions():
    """遍历所有线路，归还可脱离调度的车辆。"""
    for target_rk in ALL_ROUTE_KEYS:
        fixed = _get_fixed_bus_count(target_rk)
        if fixed == 0:
            continue
        # 目标线是否已回归平稳
        if _health_count(fixed) < _get_user_count(target_rk):
            continue

        # 找到该线路上被调度来的车
        for bus_id, (lat, lng, rk, data) in _get_real_bus_positions().items():
            effective_rk = rk or ""
            if effective_rk != target_rk:
                continue
            if "original_route_key" not in data or not data.get("original_route_key"):
                continue
            if data.get("pending_return"):
                # 已标记归还：检查是否跑完一圈（简单处理：标记后经过 circle_time 即归还）
                tagged_at = float(data.get("pending_return_tagged_at", 0))
                if tagged_at and (time.time() - tagged_at) >= get_route_circle_time(target_rk):
                    _execute_return(bus_id, data)
                continue
            # 标记 pending_return
            data["pending_return"] = True
            data["pending_return_tagged_at"] = time.time()
            redis_client.hset("bus:status:all", bus_id, json.dumps(data))
            print(f"📋 标记归还: {bus_id} 待跑完 {target_rk} 后归还 {data.get('original_route_key')}")


# ============================================================================
# 调度引擎 — 后台轮询主循环
# ============================================================================

async def _scan_and_dispatch():
    """单次调度扫描：清理 → 归还 → 抽调。"""
    _evict_expired_passengers()
    _check_all_return_conditions()
    _check_all_dispatch_conditions()


async def dispatch_scanner():
    """后台任务：每 30 秒执行一次调度扫描。"""
    while True:
        try:
            await _scan_and_dispatch()
        except Exception as e:
            print(f"⚠️ 调度扫描异常: {e}")
        await asyncio.sleep(DISPATCH_SCAN_INTERVAL)


# ============================================================================
# Pydantic 请求模型 (调度接口专用)
# ============================================================================

class PassengerActionRequest(BaseModel):
    passenger_id: str
    route_key: str
    action: str          # 'join' | 'leave'
    station_id: str | None = None


# ============================================================================
# FastAPI 应用
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库、Redis 状态，并启动后台调度轮询。"""
    global _sim_t0
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

        # 清理上次运行的残留数据，确保每次启动从零开始
        redis_client.delete("bus:status:all")
        redis_client.delete("route:bus_count")
        redis_client.delete("route:fixed_bus_count")
        redis_client.delete("route:user_count")
        # 清理所有乘客 lifecycle 记录
        for stale_key in redis_client.scan_iter("user:lifecycle:*"):
            redis_client.delete(stale_key)
        print("🧹 已清空上次残留的车队/乘客/坐标缓存")

        # 初始化线路车辆基数
        counts: dict[str, int] = {}
        for bus in BUS_FLEET:
            rk = bus["route_key"]
            counts[rk] = counts.get(rk, 0) + 1
        for rk, cnt in counts.items():
            redis_client.hset("route:bus_count", rk, str(cnt))
            redis_client.hset("route:fixed_bus_count", rk, str(cnt))
        print(f"📊 线路车辆基数已同步至 Redis（{len(counts)} 条线路）")
    except Exception:
        print("⚠️ Redis 连接失败，请检查服务是否启动")

    _sim_t0 = time.time()
    print(f"🚌 发车模拟器已启动（{len(BUS_FLEET)} 辆虚拟公交）")

    # 启动后台调度扫描
    scanner_task = asyncio.create_task(dispatch_scanner())
    print(f"🔁 调度扫描器已启动（间隔 {DISPATCH_SCAN_INTERVAL}s）")

    yield

    # 关闭
    scanner_task.cancel()
    try:
        await scanner_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Optibus Backend", lifespan=lifespan)

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
    return {"message": "Welcome to OptiBus backend", "status": "ok"}


@app.get("/health")
async def health():
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


# ==================== 管理员端 HTTP 接口 ====================

@app.post("/api/admin/login")
async def admin_login():
    return {"token": "admin_mock_token_888"}


# ==================== 司机端 HTTP 接口 ====================

@app.post("/api/driver/check_in")
async def driver_check_in(data: schemas.DriverDailyCheckIn):
    driver_id = str(data.driver_id)
    initial_status = json.dumps({
        "route_id": data.route_id,
        "lat": 0.0,
        "lng": 0.0,
        "status": "idle",
    })
    redis_client.hset("bus:status:all", driver_id, initial_status)
    redis_client.sadd(f"route:buses:{data.route_id}", driver_id)
    return {
        "status": "ok",
        "driver_id": data.driver_id,
        "route_id": data.route_id,
    }


# ==================== 调度引擎 — 乘客生命周期接口 ====================

@app.post("/api/dispatch/passenger_action")
async def passenger_action(req: PassengerActionRequest):
    """乘客加入/离开排队。

    - join: 记录 lifecycle，route:user_count +1
    - leave: 清理 lifecycle，route:user_count -1
    每个乘客同时只能存在于一条线路。
    """
    lifecycle_key = f"{LIFECYCLE_KEY_PREFIX}{req.passenger_id}"

    if req.action == "join":
        if req.route_key not in ROUTES_SEQUENCE:
            return {"status": "error", "message": f"未知线路: {req.route_key}"}

        # 防刷：检查是否已在其他线路
        existing = redis_client.get(lifecycle_key)
        if existing:
            try:
                old = json.loads(existing)
                old_rk = old.get("route_key", "")
            except json.JSONDecodeError:
                old_rk = ""
            if old_rk and old_rk != req.route_key:
                redis_client.hincrby("route:user_count", old_rk, -1)
                cnt = int(redis_client.hget("route:user_count", old_rk) or 0)
                if cnt < 0:
                    redis_client.hset("route:user_count", old_rk, "0")

        # 写入 lifecycle
        record = {
            "passenger_id": req.passenger_id,
            "route_key": req.route_key,
            "station_id": req.station_id or "",
            "join_time": time.time(),
        }
        redis_client.set(lifecycle_key, json.dumps(record))

        # 原子 +1
        redis_client.hincrby("route:user_count", req.route_key, 1)

        return {
            "status": "ok",
            "action": "join",
            "passenger_id": req.passenger_id,
            "route_key": req.route_key,
            "current_count": int(redis_client.hget("route:user_count", req.route_key) or 0),
        }

    elif req.action == "leave":
        existing = redis_client.get(lifecycle_key)
        route_to_decr = req.route_key
        if existing:
            try:
                old = json.loads(existing)
                route_to_decr = old.get("route_key", req.route_key)
            except json.JSONDecodeError:
                pass

        redis_client.delete(lifecycle_key)
        redis_client.hincrby("route:user_count", route_to_decr, -1)
        cnt = int(redis_client.hget("route:user_count", route_to_decr) or 0)
        if cnt < 0:
            redis_client.hset("route:user_count", route_to_decr, "0")

        return {
            "status": "ok",
            "action": "leave",
            "passenger_id": req.passenger_id,
            "route_key": route_to_decr,
            "current_count": max(0, cnt),
        }

    return {"status": "error", "message": f"未知 action: {req.action}"}


# ==================== 车辆位置查询接口 ====================

@app.get("/api/buses/locations")
async def get_bus_locations():
    """全网车辆实时位置 —— 拓扑格式 (fromStation, toStation 不含拐点，progress 离散化)。"""
    result: list[dict] = []

    # ---------- 真车 ----------
    all_buses = redis_client.hgetall("bus:status:all")
    for driver_id, raw_json in all_buses.items():
        try:
            data = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            continue

        lat = data.get("lat", 0.0)
        lng = data.get("lng", 0.0)

        # 解析 route_key
        rk = data.get("route_key") or data.get("current_route_key") or ""
        if not rk or rk not in ROUTES_SEQUENCE:
            route_id = data.get("route_id", 0)
            candidates = [k for k in ALL_ROUTE_KEYS if str(route_id) in k]
            if candidates:
                best_d = float("inf")
                for c in candidates:
                    _, d, _ = snap_vehicle(lat, lng, c)
                    if d < best_d:
                        best_d = d
                        rk = c

        if not rk or rk not in ROUTES_SEQUENCE:
            continue

        route = ROUTES_SEQUENCE[rk]
        seg_idx, _, _dist_to_end = snap_vehicle(lat, lng, rk)

        # 过滤拐点：前后各找到第一个真实站点
        from_station = _prev_real_station(route, seg_idx)
        to_station = _next_real_station(route, seg_idx)

        if from_station == to_station:
            continue

        # 到站判定（仅对真实站点）
        dist_from = get_distance((lat, lng), STATIONS_XY[from_station])
        dist_to = get_distance((lat, lng), STATIONS_XY[to_station])
        if dist_from < STATION_THRESHOLD:
            status = "arrived"
            progress = 0.0
        elif dist_to < STATION_THRESHOLD:
            status = "arrived"
            progress = 1.0
        else:
            status = "in-transit"
            progress = 0.5  # 离散化：行驶中固定画在中点

        route_name = rk.replace("_cw", "").replace("_ccw", "")
        display_name = {"line1": "1号线", "line2": "2号线", "teacher": "教师专线"}.get(route_name, rk)
        result.append({
            "busId": driver_id,
            "line": display_name,
            "fromStation": from_station,
            "toStation": to_station,
            "progress": progress,
            "status": status,
        })

    # ---------- 仿真车 ----------
    if _sim_t0 is not None:
        elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
        for bus in BUS_FLEET:
            if any(b["busId"] == bus["busId"] for b in result):
                continue
            seg = get_simulated_segment_info(bus, elapsed)
            if seg is None:
                continue
            from_station, to_station, progress, status = seg

            route_name = bus["route_key"].replace("_cw", "").replace("_ccw", "")
            display_name = {"line1": "1号线", "line2": "2号线", "teacher": "教师专线"}.get(route_name, route_name)
            result.append({
                "busId": bus["busId"],
                "line": display_name,
                "fromStation": from_station,
                "toStation": to_station,
                "progress": progress,
                "status": status,
            })

    return {"buses": result}


# ==================== ETA 接口 ====================

@app.get("/api/eta/{station_id}")
async def get_eta(station_id: str, route: str | None = None):
    """查询最近一班车到达指定站点的 ETA（分钟）。

    可选 query 参数 route（如 ?route=line1_cw）限定只计算指定线路的车辆。
    """
    if station_id not in STATIONS_XY:
        return {"error": f"未知站点: {station_id}"}

    # 若指定 route，直接以它为唯一候选；否则查全表
    if route:
        if route not in ROUTES_SEQUENCE:
            return {"error": f"未知线路: {route}"}
        candidate_routes = [route]
    else:
        station_route_map = build_station_route_map()
        candidate_routes = station_route_map.get(station_id, [])

    if not candidate_routes:
        return {"stationId": station_id, "etaMinutes": None, "busId": None,
                "message": "无线路经过此站"}

    best_eta = float("inf")
    best_bus_id = None

    # ---------- 真车 ----------
    all_buses = redis_client.hgetall("bus:status:all")
    for driver_id, raw_json in all_buses.items():
        try:
            data = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            continue
        lat = data.get("lat", 0.0)
        lng = data.get("lng", 0.0)
        route_id = data.get("route_id", 0)
        rk = data.get("route_key") or data.get("current_route_key") or ""

        # 解析匹配的路线键
        if rk and rk in ROUTES_SEQUENCE:
            matching_keys = [rk]
        else:
            matching_keys = [r for r in candidate_routes
                             if str(route_id) in r or r.startswith(f"line{route_id}")]
        if not matching_keys:
            matching_keys = [r for r in candidate_routes]

        # 线路过滤：仅计算请求指定的 route
        for mk in matching_keys:
            if route and mk != route:
                continue
            eta = calculate_eta(lat, lng, mk, station_id)
            if eta is not None and eta < best_eta:
                best_eta = eta
                best_bus_id = driver_id

    # ---------- 仿真车 ----------
    if best_bus_id is None and _sim_t0 is not None:
        elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
        for bus in BUS_FLEET:
            # 线路过滤
            if route and bus["route_key"] != route:
                continue
            if not route and bus["route_key"] not in candidate_routes:
                continue
            pos = get_simulated_position(bus, elapsed)
            if pos is None:
                continue
            eta = calculate_eta(pos[0], pos[1], bus["route_key"], station_id)
            if eta is not None and eta < best_eta:
                best_eta = eta
                best_bus_id = bus["busId"]

    if best_bus_id is None:
        return {"stationId": station_id, "etaMinutes": None, "busId": None,
                "message": "暂无可用车辆"}
    return {
        "stationId": station_id,
        "etaMinutes": best_eta,
        "busId": best_bus_id,
    }


# ==================== 调度引擎 — 管理接口 ====================

@app.get("/api/dispatch/status")
async def dispatch_status():
    """查看全网调度状态（调试用）。"""
    routes_status = []
    for rk in ALL_ROUTE_KEYS:
        routes_status.append({
            "route_key": rk,
            "user_count": _get_user_count(rk),
            "bus_count": _get_bus_count(rk),
            "fixed_bus_count": _get_fixed_bus_count(rk),
            "health_line": _health_count(_get_bus_count(rk)),
            "overcrowded": _is_overcrowded(rk),
            "can_spare": _can_spare_bus(rk),
            "circle_time_s": round(get_route_circle_time(rk), 1),
        })

    dispatched_buses = []
    for bus_id, (lat, lng, rk, data) in _get_real_bus_positions().items():
        if data.get("original_route_key") or data.get("pending_return"):
            dispatched_buses.append({
                "busId": bus_id,
                "current_route": rk,
                "original_route": data.get("original_route_key"),
                "pending_return": data.get("pending_return", False),
            })

    return {
        "routes": routes_status,
        "dispatched_buses": dispatched_buses,
    }


# ==================== WebSocket 路由 ====================

@app.websocket("/ws/driver/{driver_id}")
async def driver_websocket(websocket: WebSocket, driver_id: int):
    driver_id_str = str(driver_id)
    await manager.connect(websocket, "driver", driver_id_str)
    try:
        while True:
            raw = await websocket.receive_json()
            loc = schemas.LocationUpdate(**raw)
            current = redis_client.hget("bus:status:all", driver_id_str)
            if current:
                status_data = json.loads(current)
            else:
                status_data = {"route_id": 0}
            status_data["lat"] = loc.lat
            status_data["lng"] = loc.lng
            status_data["status"] = "driving"
            redis_client.hset("bus:status:all", driver_id_str, json.dumps(status_data))
    except WebSocketDisconnect:
        manager.disconnect("driver", driver_id_str)
    except Exception:
        manager.disconnect("driver", driver_id_str)


@app.websocket("/ws/passenger/{client_id}")
async def passenger_websocket(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, "passenger", client_id)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager.disconnect("passenger", client_id)
    except Exception:
        manager.disconnect("passenger", client_id)
