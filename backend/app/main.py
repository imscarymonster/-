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
    "拐点8": (420, 120), "拐点9": (520, 450),
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
        "拐点2", "拐点1", "拐点3", "拐点8", "1号食堂", "自强路站",
        "拐点8", "拐点3", "中传专享楼",
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

# 仿真车 ID 集合（模块级，供调度引擎判断是否为仿真车）
SIM_BUS_IDS = {b["busId"] for b in BUS_FLEET}

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

# 调度事件队列（sync 函数收集，_scan_and_dispatch 异步推送 WebSocket）
_dispatch_events: list[dict] = []

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
    """基于连续物理坐标的平滑位置计算 —— 彻底消除离散 tick 跳跃。

    通过 get_simulated_position 获取车辆在完整路线（含拐点）上的精确
    物理坐标，再过滤到真实站点，计算连续 progress，使前端渲染平滑连贯。

    Returns:
        (fromStation, toStation, progress, status) 或 None
    """
    route_key = bus["route_key"]
    full_route = ROUTES_SEQUENCE.get(route_key)
    if not full_route or len(full_route) < 2:
        return None

    # 1. 获取连续物理坐标
    pos = get_simulated_position(bus, elapsed_s)
    if pos is None:
        return None

    # 2. 吸附到路线段
    seg_idx, _best_dist, _to_end = snap_vehicle(pos[0], pos[1], route_key)

    # 3. 过滤拐点 → 真实站点
    from_station = _prev_real_station(full_route, seg_idx)
    to_station = _next_real_station(full_route, seg_idx)

    if from_station == to_station:
        return None

    # 4. 计算连续 progress：车辆在 from→to 真实站点间的精确位置
    fx, fy = STATIONS_XY[from_station]
    tx, ty = STATIONS_XY[to_station]

    # 累加 from→to 沿完整路线的距离（含拐点），计算车辆已走比例
    total_seg_dist = 0.0
    accumulated = 0.0
    seg_start_idx = None
    seg_end_idx = None

    # 找到 from 和 to 在完整路线中的位置
    n = len(full_route)
    for i in range(n):
        if full_route[i] == from_station:
            seg_start_idx = i
            break
    for i in range(seg_start_idx + 1 if seg_start_idx is not None else 0, seg_start_idx + n + 1 if seg_start_idx is not None else n):
        idx = i % n
        if full_route[idx] == to_station:
            seg_end_idx = idx
            break

    if seg_start_idx is None or seg_end_idx is None:
        return None

    # 计算 from→to 总距离
    cursor = seg_start_idx
    while cursor % n != seg_end_idx:
        a = STATIONS_XY[full_route[cursor % n]]
        b = STATIONS_XY[full_route[(cursor + 1) % n]]
        total_seg_dist += get_distance(a, b)
        cursor += 1

    if total_seg_dist == 0:
        progress = 1.0
    else:
        # 计算车辆当前位置到 from 的累计距离
        cursor = seg_start_idx
        while cursor % n != seg_end_idx:
            a = STATIONS_XY[full_route[cursor % n]]
            b = STATIONS_XY[full_route[(cursor + 1) % n]]
            seg_d = get_distance(a, b)
            # 检查车辆是否在当前子段
            if cursor == seg_idx:
                # 车辆在当前子段上
                proj_x, proj_y, _, _ = point_to_segment_projection(
                    pos[0], pos[1], a[0], a[1], b[0], b[1])
                accumulated += get_distance(a, (proj_x, proj_y))
                break
            else:
                accumulated += seg_d
            cursor += 1

        progress = min(1.0, max(0.0, accumulated / total_seg_dist))

    # 5. 到站判定
    dist_to_to = get_distance(pos, (tx, ty))
    if dist_to_to < STATION_THRESHOLD:
        status = "arrived"
        progress = 1.0
    elif get_distance(pos, (fx, fy)) < STATION_THRESHOLD:
        status = "arrived"
        progress = 0.0
    else:
        status = "in-transit"

    return (from_station, to_station, progress, status)


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


def _get_route_direction(route_key: str) -> str:
    """提取路线方向后缀（_cw 或 _ccw）。"""
    if route_key.endswith("_cw"):
        return "_cw"
    if route_key.endswith("_ccw"):
        return "_ccw"
    return ""


def _find_fastest_bus_to_hub(source_route_key: str) -> str | None:
    """在闲线上找到最快能到达中转站『中传专享楼』的车（按 ETA 排序）。"""
    HUB = "中传专享楼"
    best_bus_id: str | None = None
    best_eta: float = float("inf")

    # 真车
    for bus_id, (lat, lng, rk, data) in _get_real_bus_positions().items():
        if rk != source_route_key:
            continue
        if data.get("pending_return") or data.get("pending_dispatch_to") or data.get("original_route_key"):
            continue
        if time.time() - data.get("dispatch_timestamp", 0) < 60:
            continue
        eta = calculate_eta(lat, lng, source_route_key, HUB)
        if eta is not None and eta < best_eta:
            best_eta = eta
            best_bus_id = bus_id

    # 仿真车
    if best_bus_id is None and _sim_t0 is not None:
        elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
        for b in BUS_FLEET:
            if b["route_key"] != source_route_key:
                continue
            pos = get_simulated_position(b, elapsed)
            if pos is None:
                continue
            eta = calculate_eta(pos[0], pos[1], source_route_key, HUB)
            if eta is not None and eta < best_eta:
                best_eta = eta
                best_bus_id = b["busId"]

    return best_bus_id


def _resolve_dispatch_target(target_route_key: str, source_route_key: str) -> str:
    """直接返回目标线路，不做方向继承。

    调度逻辑：支援车去目标线的顺/逆方向由目标线自身需求决定，
    不应继承源车方向。target_route_key 已经是具体方向（如 line1_cw）。
    """
    return target_route_key


# ============================================================================
# 调度引擎 — 两段式变线（阶段 A：打标记；阶段 B：到站变装）
# ============================================================================

def _mark_dispatch_candidate(target_route_key: str, source_route_key: str) -> bool:
    """阶段 A：选定闲线上 ETA 最短的车，打 pending_dispatch_to 标记。

    车辆仍沿原线行驶，绝不瞬移！变线在到达中转站时才执行。
    """
    bus_id = _find_fastest_bus_to_hub(source_route_key)
    if bus_id is None:
        return False

    raw = redis_client.hget("bus:status:all", bus_id)
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    # 记录老东家
    if "original_route_key" not in data or not data.get("original_route_key"):
        data["original_route_key"] = source_route_key

    # 方向继承：目标线前缀 + 源车方向后缀
    pending_target = _resolve_dispatch_target(target_route_key, source_route_key)

    data["pending_dispatch_to"] = pending_target
    data["transfer_station"] = "中传专享楼"
    data["status"] = "dispatched"
    redis_client.hset("bus:status:all", bus_id, json.dumps(data))

    # 记录调度事件，稍后通过 WebSocket 推送给司机
    _dispatch_events.append({
        "busId": bus_id,
        "action": "dispatch_marked",
        "fromRoute": source_route_key,
        "toRoute": pending_target,
    })

    print(f"📋 标记调度: {bus_id} ({source_route_key}) → {pending_target}，待到达中传专享楼")
    return True


def _distance_along_route(route_key: str, target_station: str) -> float:
    """计算从路线起点到 target_station 首次出现的累计距离 (米)。"""
    route = ROUTES_SEQUENCE[route_key]
    total = 0.0
    for i in range(len(route) - 1):
        if route[i] == target_station:
            return total
        total += get_distance(STATIONS_XY[route[i]], STATIONS_XY[route[i + 1]])
    return total


def _recalibrate_sim_bus(bus_id: str, new_route_key: str):
    """重置仿真车的 departure_offset_s，使其在新路线上位于中传专享楼且平滑向前。

    使用 tick 系统对齐：target_tick = 2 * hub_idx + 已完成周期 * 周期tick数。
    确保 bus 在下一个 tick 能平滑过渡到 in-transit 状态。
    """
    if _sim_t0 is None:
        return
    pure = REAL_ROUTES.get(new_route_key, [])
    if not pure or "中传专享楼" not in pure:
        return

    hub_idx = pure.index("中传专享楼")
    TICK_S = 15
    cycle_ticks = len(pure) * 2          # 一个完整周期的 tick 数
    cycle_time = cycle_ticks * TICK_S    # 一个周期秒数

    elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
    base_travel = hub_idx * 2 * TICK_S   # 到达 hub_idx 所需秒数
    current_cycle = int(elapsed / cycle_time) if cycle_time > 0 else 0
    travel_t = current_cycle * cycle_time + base_travel
    new_offset = elapsed - travel_t

    for b in BUS_FLEET:
        if b["busId"] == bus_id:
            b["route_key"] = new_route_key
            b["departure_offset_s"] = new_offset
            print(f"🔄 仿真校准: {bus_id} → {new_route_key}, hub_idx={hub_idx}, "
                  f"cycle={current_cycle}, offset={new_offset:.1f}s")
            return


def _check_pending_dispatches():
    """阶段 B：检测已标记车辆是否到达中转站，执行变线 + 基数同步。"""
    HUB = "中传专享楼"
    hub_xy = STATIONS_XY[HUB]

    for bus_id, (lat, lng, _rk, data) in _get_real_bus_positions().items():
        pending_target = data.get("pending_dispatch_to")
        if not pending_target or pending_target not in ROUTES_SEQUENCE:
            continue

        if get_distance((lat, lng), hub_xy) < STATION_THRESHOLD:
            original = data.get("original_route_key", "")

            # 执行变线
            data["route_key"] = pending_target
            data["current_route_key"] = pending_target
            data.pop("pending_dispatch_to", None)
            data.pop("transfer_station", None)
            data["status"] = "driving"
            data["dispatch_timestamp"] = time.time()
            # 仿真车直接标记 running（无真实 GPS 驱动 _update_lap_state）
            data["lap_state"] = "running" if bus_id in SIM_BUS_IDS else "just_started"
            redis_client.hset("bus:status:all", bus_id, json.dumps(data))

            # 原子基数同步（此时才做！）
            if original:
                redis_client.hincrby("route:bus_count", original, -1)
                cnt = int(redis_client.hget("route:bus_count", original) or 0)
                if cnt < 0:
                    redis_client.hset("route:bus_count", original, "0")
            redis_client.hincrby("route:bus_count", pending_target, 1)

            # 重置 BUS_FLEET 中的仿真时空原点（防止坐标越界崩溃）
            _recalibrate_sim_bus(bus_id, pending_target)

            # 记录调度执行事件，稍后 WebSocket 推送司机端触发 TTS
            _dispatch_events.append({
                "busId": bus_id,
                "action": "dispatch_executed",
                "fromRoute": original,
                "toRoute": pending_target,
            })

            print(f"🚛 到站变线: {bus_id} 从 {original} → {pending_target}（到达中传专享楼）")


# ============================================================================
# 调度引擎 — 脱离调度 (Return)
# ============================================================================

def _execute_return(bus_id: str, data: dict):
    """将一台被调度车归还其原始线路 —— 彻底清零，无缝接轨。"""
    original = data.get("original_route_key")
    current = data.get("route_key") or data.get("current_route_key")
    if not original or not current:
        return

    # 恢复 route_key
    data["route_key"] = original
    data["current_route_key"] = original

    # 彻底清除所有调度残余标记
    for tag in ("original_route_key", "pending_return", "lap_state",
                "pending_dispatch_to", "transfer_station",
                "pending_return_tagged_at", "pending_dispatch_tagged_at"):
        data.pop(tag, None)

    # 归还冷却锁：刷新时间戳，60s 内禁止再次被抽调
    data["dispatch_timestamp"] = time.time()
    data["status"] = "driving"
    redis_client.hset("bus:status:all", bus_id, json.dumps(data))

    # 基数同步：目标线 -1，原线 +1
    redis_client.hincrby("route:bus_count", current, -1)
    redis_client.hincrby("route:bus_count", original, 1)

    for rk in (current, original):
        cnt = int(redis_client.hget("route:bus_count", rk) or 0)
        if cnt < 0:
            redis_client.hset("route:bus_count", rk, "0")

    print(f"🏠 归还: {bus_id} 从 {current} → 原线路 {original}（冷却60s，标签清零）")


# ============================================================================
# 调度引擎 — 乘客生命周期清理
# ============================================================================

def _evict_expired_passengers():
    """扫描 dispatch:passengers Hash，静默清理超时用户。

    优化：真车位置和仿真状态只读取一次，缓存后复用，避免 N+1 Redis 查询。
    """
    now = time.time()
    evicted = 0

    # ---- 一次性缓存：真车位置 + 仿真状态 ----
    real_positions = _get_real_bus_positions()
    sim_elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP if _sim_t0 else 0.0
    # 预计算所有仿真车位置
    sim_positions: dict[str, tuple[float, float]] = {}
    if _sim_t0:
        for b in BUS_FLEET:
            pos = get_simulated_position(b, sim_elapsed)
            if pos:
                sim_positions[b["busId"]] = (pos[0], pos[1], b["route_key"])

    all_passengers = redis_client.hgetall("dispatch:passengers")
    for user_id, raw in all_passengers.items():
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            redis_client.hdel("dispatch:passengers", user_id)
            continue

        join_time = data.get("join_time", 0)
        route_key = data.get("route_key", "")
        station_id = data.get("station_id", "")

        if not route_key or route_key not in ROUTES_SEQUENCE:
            redis_client.hdel("dispatch:passengers", user_id)
            continue

        user_elapsed = now - join_time

        # 用缓存数据计算 ETA（不再逐次调 Redis）
        best_eta = 999
        tx, ty = STATIONS_XY.get(station_id, (0, 0))
        for _bid, (lat, lng, rk, bdata) in real_positions.items():
            if rk == route_key and not bdata.get("pending_return"):
                eta = calculate_eta(lat, lng, route_key, station_id)
                if eta is not None and eta < best_eta:
                    best_eta = eta
        if best_eta == 999:
            for bid, (sx, sy, srk) in sim_positions.items():
                if srk == route_key:
                    eta = calculate_eta(sx, sy, route_key, station_id)
                    if eta is not None and eta < best_eta:
                        best_eta = eta

        eta_seconds = max(0, (best_eta if best_eta != 999 else 0)) * 60
        circle_time = get_route_circle_time(route_key)
        retention = eta_seconds + circle_time

        if user_elapsed >= retention:
            redis_client.hdel("dispatch:passengers", user_id)
            redis_client.hincrby("route:user_count", route_key, -1)
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
    """遍历所有线路，对过载线寻找闲线并标记候选车辆（阶段 A）。

    选车标准：ETA 最短到达中转站『中传专享楼』的车。
    """
    for target_rk in ALL_ROUTE_KEYS:
        if not _is_overcrowded(target_rk):
            continue

        # 排除自身 + 同线反向（line1_ccw 不能支援 line1_cw，否则是左手倒右手）
        target_base = target_rk.rstrip("_cw").rstrip("_ccw")
        candidates = [rk for rk in ALL_ROUTE_KEYS
                      if rk != target_rk
                      and not rk.startswith(target_base)
                      and _can_spare_bus(rk)]
        if not candidates:
            continue

        # 逐闲线尝试标记，直到目标线恢复健康
        for src_rk in candidates:
            if not _is_overcrowded(target_rk):
                break
            if not _can_spare_bus(src_rk):
                continue
            _mark_dispatch_candidate(target_rk, src_rk)


def _check_all_return_conditions():
    """一圈防抖归还：支援车必须在新线上完整跑完一圈，再回中传专享楼才归还。

    条件：
    1. original_route_key 标签存在
    2. lap_state == "running"（已驶离枢纽，跑完至少一圈）
    3. 距离中传专享楼 < 20m（刚好回到枢纽）
    4. dispatch_timestamp >= 60s 冷却（防止刚变线就误判）
    """
    HUB = "中传专享楼"
    hub_xy = STATIONS_XY[HUB]

    for bus_id, (lat, lng, _rk, data) in _get_real_bus_positions().items():
        original = data.get("original_route_key")
        if not original or original not in ROUTES_SEQUENCE:
            continue

        # 一圈防抖：必须是 running 状态
        if data.get("lap_state") != "running":
            continue

        # 冷却拦截
        if time.time() - data.get("dispatch_timestamp", 0) < 60:
            continue

        # 仿真车用模拟位置判距，真车用 Redis GPS 坐标
        if bus_id in SIM_BUS_IDS and _sim_t0 is not None:
            elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
            sim_pos = get_simulated_position(
                next((b for b in BUS_FLEET if b["busId"] == bus_id), None) or {},
                elapsed)
            if sim_pos is None or get_distance(sim_pos, hub_xy) >= STATION_THRESHOLD:
                continue
        else:
            # 必须回到枢纽站
            if get_distance((lat, lng), hub_xy) >= STATION_THRESHOLD:
                continue

        # 执行归还 + 仿真校准
        _execute_return(bus_id, data)
        _recalibrate_sim_bus(bus_id, original)


# ============================================================================
# 调度引擎 — 后台轮询主循环
# ============================================================================

def _update_lap_state():
    """驶离检测：just_started 且距枢纽 >200m → running（确认已开出）。"""
    HUB = "中传专享楼"
    hub_xy = STATIONS_XY[HUB]
    DEPART_DIST = 200.0  # 驶离判定距离 (m)

    for bus_id, (lat, lng, _rk, data) in _get_real_bus_positions().items():
        if data.get("lap_state") != "just_started":
            continue
        if get_distance((lat, lng), hub_xy) > DEPART_DIST:
            data["lap_state"] = "running"
            redis_client.hset("bus:status:all", bus_id, json.dumps(data))
            print(f"🏃 驶离确认: {bus_id} lap_state → running")


async def _scan_and_dispatch():
    """单次调度扫描：清理 → 归还 → 到站变线(阶段B) → 驶离检测 → 打标记(阶段A)。

    所有同步 Redis 操作通过 asyncio.to_thread 在线程池中执行，
    避免阻塞 FastAPI 的 asyncio 事件循环。
    """
    global _dispatch_events
    _dispatch_events = []  # 清空事件队列

    await asyncio.to_thread(_evict_expired_passengers)
    await asyncio.to_thread(_check_all_return_conditions)
    await asyncio.to_thread(_update_lap_state)
    await asyncio.to_thread(_check_all_dispatch_conditions)   # 阶段 A：先打标记
    await asyncio.to_thread(_check_pending_dispatches)       # 阶段 B：后执行到站变线

    # ---- 异步推送调度通知给司机端（触发 TTS 语音播报） ----
    for event in _dispatch_events:
        bus_id = event["busId"]
        action = event["action"]
        from_rk = event.get("fromRoute", "")
        to_rk = event.get("toRoute", "")

        # 路线名转中文
        def _rk_display(rk):
            for prefix, name in [("line1", "1号线"), ("line2", "2号线"), ("teacher", "教师专线")]:
                if rk.startswith(prefix):
                    return name
            return rk

        if action == "dispatch_marked":
            text = (
                f"紧急调度指令：系统检测到{_rk_display(to_rk)}客流拥挤。"
                f"请在送完本车乘客后，立即前往中传专享楼，变更路线至{_rk_display(to_rk)}支援！"
            )
        elif action == "dispatch_executed":
            text = (
                f"调度执行完毕：您的车辆已正式变更为{_rk_display(to_rk)}。"
                f"请按照新路线继续行驶。导航指令已同步至您的终端。"
            )
        else:
            text = f"收到调度指令：{action} {_rk_display(to_rk)}"

        try:
            from .websocket import manager
            await manager.send_to_driver(bus_id, {
                "type": "dispatch",
                "action": action,
                "fromRoute": from_rk,
                "toRoute": to_rk,
                "message": text,
            })
            print(f"📢 已推送调度通知给司机 {bus_id}: {action}")
        except Exception as e:
            print(f"⚠️ 推送调度通知失败 ({bus_id}): {e}")
        # 同时广播给所有在线司机（演示用，确保有人收到）
        try:
            from .websocket import manager
            await manager.broadcast_drivers({
                "type": "dispatch",
                "action": action,
                "fromRoute": from_rk,
                "toRoute": to_rk,
                "message": text,
                "targetBus": bus_id,
            })
        except Exception:
            pass


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
    user_id: str = ""              # 前端新字段名
    passenger_id: str = ""         # 向后兼容旧字段名
    route_key: str
    action: str                    # 'join' | 'leave'
    station_id: str | None = None

    @property
    def pid(self) -> str:
        """统一返回有效用户 ID（优先 user_id，兜底 passenger_id）。"""
        return self.user_id or self.passenger_id


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
        redis_client.delete("dispatch:passengers")
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

@app.post("/api/driver/sign_off")
async def driver_sign_off(data: dict):
    """司机签退：从 Redis 清除车辆状态，线路车辆数 -1。"""
    bus_id = str(data.get("busId", ""))
    if not bus_id:
        return {"status": "error", "message": "缺少 busId"}

    raw = redis_client.hget("bus:status:all", bus_id)
    route_key = ""
    if raw:
        try:
            status_data = json.loads(raw)
            route_key = status_data.get("route_key", "")
        except json.JSONDecodeError:
            pass

    redis_client.hdel("bus:status:all", bus_id)

    if route_key:
        redis_client.hincrby("route:bus_count", route_key, -1)
        cnt = int(redis_client.hget("route:bus_count", route_key) or 0)
        if cnt < 0:
            redis_client.hset("route:bus_count", route_key, "0")

    return {"status": "ok", "message": f"司机 {bus_id} 已签退", "routeKey": route_key}


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


# ============================================================================
# GPS → 米制坐标转换（校园地图参考系）
# ============================================================================

# 校园参考点 GPS（海南陵水黎安国际教育创新试验区，需实地校准）
GPS_REF_LAT = 18.4300
GPS_REF_LNG = 110.0000
METERS_PER_DEG_LAT = 111320.0
METERS_PER_DEG_LNG = 105600.0  # cos(18.43°) × 111320


def gps_to_meters(lat: float, lng: float) -> tuple[float, float]:
    """将真实 GPS 经纬度转换为校园米制坐标 (x, y)。"""
    x = (lng - GPS_REF_LNG) * METERS_PER_DEG_LNG
    y = (lat - GPS_REF_LAT) * METERS_PER_DEG_LAT
    return (x, y)


def _route_key_to_route_id(route_key: str) -> int:
    """从 route_key 反查数字 route_id（兼容 check_in 格式）。"""
    for prefix, rid in [("line1", 1), ("line2", 2), ("teacher", 3)]:
        if route_key.startswith(prefix):
            return rid
    return 0


@app.post("/api/buses/location/update")
async def bus_location_update(data: dict):
    """接收司机手机 GPS 定位，转换为校园米制坐标后存入 Redis。

    POST body:
    {
        "busId": "driver01",
        "lat": 18.4305,       // 浏览器 GPS 纬度
        "lng": 110.0020,      // 浏览器 GPS 经度
        "status": "driving",
        "routeKey": "line2_cw" // 可选：司机所在线路
    }
    """
    bus_id = str(data.get("busId", ""))
    if not bus_id:
        return {"status": "error", "message": "缺少 busId"}

    gps_lat = float(data.get("lat", 0))
    gps_lng = float(data.get("lng", 0))

    # GPS → 米制坐标
    meter_x, meter_y = gps_to_meters(gps_lat, gps_lng)

    # 校验 GPS 是否在校园附近（±0.05° ≈ 5km），桌面浏览器定位不准时 fallback
    gps_near_campus = (
        abs(gps_lat - GPS_REF_LAT) < 0.05 and
        abs(gps_lng - GPS_REF_LNG) < 0.05 and
        gps_lat != 0 and gps_lng != 0
    )

    # 读取已有状态，或为新车上线初始化
    raw = redis_client.hget("bus:status:all", bus_id)
    if raw:
        try:
            status_data = json.loads(raw)
        except json.JSONDecodeError:
            status_data = {}
    else:
        status_data = {}
        # 新车上线：确定路线
        route_key = data.get("routeKey", "")
        if not route_key or route_key not in ROUTES_SEQUENCE:
            # 自动匹配：GPS 米制坐标最近的路线
            best_rk, best_d = None, float("inf")
            for rk in ALL_ROUTE_KEYS:
                _, d, _ = snap_vehicle(meter_x, meter_y, rk)
                if d < best_d:
                    best_d = d
                    best_rk = rk
            route_key = best_rk or "line1_cw"
        status_data["route_key"] = route_key
        status_data["route_id"] = _route_key_to_route_id(route_key)
        status_data["source"] = "gps"
        # 线路车辆计数 +1
        redis_client.hincrby("route:bus_count", route_key, 1)

    if gps_near_campus:
        status_data["lat"] = meter_x
        status_data["lng"] = meter_y
    else:
        # GPS 偏离校园太远（桌面浏览器 / IP 定位不准）：保持上次有效位置
        # 若无历史位置，则放到路线首站
        if status_data.get("lat") in (None, 0.0) and status_data.get("lng") in (None, 0.0):
            route_key = status_data.get("route_key", "line1_cw")
            if route_key in ROUTES_SEQUENCE:
                first_station = ROUTES_SEQUENCE[route_key][0]
                sx, sy = STATIONS_XY[first_station]
                status_data["lat"] = sx
                status_data["lng"] = sy
        # 否则保持上次的 lat/lng 不变

    status_data["status"] = data.get("status", "driving")

    redis_client.hset("bus:status:all", bus_id, json.dumps(status_data))

    return {
        "status": "ok",
        "busId": bus_id,
        "gps": {"lat": gps_lat, "lng": gps_lng},
        "meter": {"x": round(status_data["lat"], 1), "y": round(status_data["lng"], 1)},
        "nearCampus": gps_near_campus,
    }


# ==================== 调度引擎 — 乘客生命周期接口 ====================

@app.post("/api/dispatch/passenger_action")
async def passenger_action(req: PassengerActionRequest):
    """乘客加入/离开排队 —— 使用 dispatch:passengers Hash 瞬时记忆入库。

    - join: dispatch:passengers HSET + route:user_count +1
    - leave: dispatch:passengers HDEL + route:user_count -1
    """
    user_id = req.pid
    if not user_id:
        return {"status": "error", "message": "缺少 user_id 或 passenger_id"}

    if req.action == "join":
        if req.route_key not in ROUTES_SEQUENCE:
            return {"status": "error", "message": f"未知线路: {req.route_key}"}

        # 防刷：检查是否已在其他线路
        existing_raw = redis_client.hget("dispatch:passengers", user_id)
        if existing_raw:
            try:
                old = json.loads(existing_raw)
                old_rk = old.get("route_key", "")
            except json.JSONDecodeError:
                old_rk = ""
            if old_rk and old_rk != req.route_key:
                redis_client.hincrby("route:user_count", old_rk, -1)
                cnt = int(redis_client.hget("route:user_count", old_rk) or 0)
                if cnt < 0:
                    redis_client.hset("route:user_count", old_rk, "0")

        # 写入 Hash
        record = {
            "user_id": user_id,
            "route_key": req.route_key,
            "station_id": req.station_id or "",
            "join_time": time.time(),
        }
        redis_client.hset("dispatch:passengers", user_id, json.dumps(record))
        redis_client.hincrby("route:user_count", req.route_key, 1)

        return {
            "status": "ok",
            "action": "join",
            "user_id": user_id,
            "route_key": req.route_key,
            "current_count": int(redis_client.hget("route:user_count", req.route_key) or 0),
        }

    elif req.action == "leave":
        existing_raw = redis_client.hget("dispatch:passengers", user_id)
        route_to_decr = req.route_key
        if existing_raw:
            try:
                old = json.loads(existing_raw)
                route_to_decr = old.get("route_key", req.route_key)
            except json.JSONDecodeError:
                pass

        redis_client.hdel("dispatch:passengers", user_id)
        redis_client.hincrby("route:user_count", route_to_decr, -1)
        cnt = int(redis_client.hget("route:user_count", route_to_decr) or 0)
        if cnt < 0:
            redis_client.hset("route:user_count", route_to_decr, "0")

        return {
            "status": "ok",
            "action": "leave",
            "user_id": user_id,
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
    try:
        all_buses = redis_client.hgetall("bus:status:all")
    except Exception:
        all_buses = {}
    for driver_id, raw_json in all_buses.items():
        # 仿真车由发车模拟器提供位置，跳过调度引擎写入的 Redis 空坐标
        if driver_id in SIM_BUS_IDS:
            continue
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
            "routeKey": rk,
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
                "routeKey": bus["route_key"],
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
    try:
        all_buses = redis_client.hgetall("bus:status:all")
    except Exception:
        all_buses = {}
    for driver_id, raw_json in all_buses.items():
        if driver_id in SIM_BUS_IDS:
            continue  # 仿真车由模拟器提供位置
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

        # 兜底：若指定 route 但站点不在该线路上（前端/后端数据不一致），
        # 则回退到全网所有线路搜索，避免"暂无可用车辆"
        if best_bus_id is None and route:
            for bus in BUS_FLEET:
                pos = get_simulated_position(bus, elapsed)
                if pos is None:
                    continue
                eta = calculate_eta(pos[0], pos[1], bus["route_key"], station_id)
                if eta is not None and eta < best_eta:
                    best_eta = eta
                    best_bus_id = bus["busId"]

    # 最终兜底：孤站（不在任何路线上）用直线距离估算
    if best_bus_id is None and _sim_t0 is not None:
        elapsed = (time.time() - _sim_t0) * SIMULATION_SPEEDUP
        tx, ty = STATIONS_XY[station_id]
        for bus in BUS_FLEET:
            pos = get_simulated_position(bus, elapsed)
            if pos is None:
                continue
            d = get_distance(pos, (tx, ty))
            eta = math.ceil(d / BUS_SPEED / 60)
            if eta < best_eta:
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

@app.get("/api/dispatch/stats")
async def dispatch_stats():
    """实时排队统计 —— 返回各线路当前排队人数。"""
    try:
        raw = redis_client.hgetall("route:user_count")
    except Exception:
        return {}
    return {rk: int(cnt) for rk, cnt in raw.items()}


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


@app.get("/api/dispatch/dashboard")
async def dispatch_dashboard():
    """管理端监控看板数据：平均候车时长 + 拥堵状态。"""
    # ---- 平均候车时长 ----
    avg_minutes = 0.0
    try:
        all_passengers = redis_client.hgetall("dispatch:passengers")
        etas = []
        for user_id, raw in all_passengers.items():
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            route_key = data.get("route_key", "")
            station_id = data.get("station_id", "")
            if route_key in ROUTES_SEQUENCE and station_id in STATIONS_XY:
                eta = _get_min_eta_for_station(route_key, station_id)
                if eta > 0:
                    etas.append(eta)
        if etas:
            avg_minutes = round(sum(etas) / len(etas), 1)
    except Exception:
        avg_minutes = 0.0

    # ---- 拥堵状态 ----
    congestion = []
    for rk in ALL_ROUTE_KEYS:
        if "_cw" not in rk:
            continue  # 只检查顺时针线路（去重）
        if _is_overcrowded(rk):
            display = rk.replace("_cw", "").replace("_ccw", "")
            name_map = {"line1": "1号线", "line2": "2号线", "teacher": "教师专线"}
            congestion.append({
                "routeKey": rk,
                "display": name_map.get(display, rk),
                "userCount": _get_user_count(rk),
                "busCount": _get_bus_count(rk),
                "healthLine": _health_count(_get_bus_count(rk)),
            })

    # ---- 各线路在线车辆数（cw + ccw 合并为线路总数） ----
    route_bus_counts = []
    try:
        raw = redis_client.hgetall("route:bus_count")
        name_map = {"line1": "1号线", "line2": "2号线", "teacher": "教师专线"}
        color_map = {"line1": "#102c4c", "line2": "#7ab829", "teacher": "#c42126"}
        for base in ["line1", "line2", "teacher"]:
            cw = int(raw.get(f"{base}_cw", 0))
            ccw = int(raw.get(f"{base}_ccw", 0))
            route_bus_counts.append({
                "routeKey": base,
                "name": name_map.get(base, base),
                "color": color_map.get(base, "#999"),
                "count": cw + ccw,
            })
    except Exception:
        pass

    return {
        "avgWaitMinutes": avg_minutes,
        "congestion": congestion,
        "routeBusCounts": route_bus_counts,
    }


@app.post("/api/dispatch/trigger_scan")
async def trigger_dispatch_scan():
    """立即执行一次调度扫描（不等 30 秒轮询）。"""
    try:
        await _scan_and_dispatch()
        return {"status": "ok", "message": "调度扫描已完成，系统已自动调配车辆。"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/dispatch/reset_line1")
async def reset_line1():
    """清除 1 号线所有排队乘客，并将从 2 号线调来的车辆归还原线路。"""
    import asyncio

    # 1. 清除 1 号线所有排队乘客
    all_passengers = redis_client.hgetall("dispatch:passengers")
    removed = 0
    for user_id, raw in all_passengers.items():
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            redis_client.hdel("dispatch:passengers", user_id)
            continue
        if data.get("route_key", "").startswith("line1"):
            redis_client.hdel("dispatch:passengers", user_id)
            removed += 1

    # 重置 1 号线排队人数
    redis_client.hset("route:user_count", "line1_cw", "0")
    redis_client.hset("route:user_count", "line1_ccw", "0")

    # 2. 找出所有从 2 号线调来的车辆，归还
    returned = 0
    for bus_id, (lat, lng, rk, data) in _get_real_bus_positions().items():
        original = data.get("original_route_key", "")
        if not original or not original.startswith("line2"):
            continue
        # 执行归还
        _execute_return(bus_id, data)
        # 仿真车校准
        if bus_id in SIM_BUS_IDS:
            _recalibrate_sim_bus(bus_id, original)
        returned += 1

    # 清除 pending_dispatch_to 标记（未到站的调度标记）
    for bus_id, (lat, lng, rk, data) in _get_real_bus_positions().items():
        if data.get("pending_dispatch_to", "").startswith("line1"):
            data.pop("pending_dispatch_to", None)
            data.pop("transfer_station", None)
            data.pop("original_route_key", None)
            data["status"] = "driving"
            redis_client.hset("bus:status:all", bus_id, json.dumps(data))

    return {
        "status": "ok",
        "message": f"已清除 {removed} 名乘客，{returned} 辆调度车已归还原线路。1号线已恢复正常。",
        "passengersRemoved": removed,
        "busesReturned": returned,
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
