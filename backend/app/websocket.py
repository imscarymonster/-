# WebSocket 网关 — 处理三端实时通信
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict


class ConnectionManager:
    """WebSocket 连接管理器 —— 按角色区分司机与乘客连接。"""

    def __init__(self):
        self.active_drivers: Dict[str, WebSocket] = {}       # driver_id → WebSocket
        self.active_passengers: Dict[str, WebSocket] = {}    # passenger_id → WebSocket

    async def connect(self, websocket: WebSocket, client_type: str, client_id: str):
        """接受 WebSocket 连接并注册到对应角色池。"""
        await websocket.accept()
        if client_type == "driver":
            self.active_drivers[client_id] = websocket
        elif client_type == "passenger":
            self.active_passengers[client_id] = websocket

    def disconnect(self, client_type: str, client_id: str):
        """从角色池中移除断开的连接。"""
        pool = self.active_drivers if client_type == "driver" else self.active_passengers
        pool.pop(client_id, None)

    async def send_message(self, websocket: WebSocket, message: dict):
        """向单个 WebSocket 连接发送 JSON 消息。"""
        await websocket.send_json(message)

    async def send_to_driver(self, driver_id: str, message: dict):
        """向指定司机推送消息。"""
        ws = self.active_drivers.get(driver_id)
        if ws:
            await ws.send_json(message)

    async def broadcast_drivers(self, message: dict):
        """向所有在线司机广播消息。"""
        for ws in self.active_drivers.values():
            await ws.send_json(message)

    async def broadcast_passengers(self, message: dict):
        """向所有在线乘客广播消息。"""
        for ws in self.active_passengers.values():
            await ws.send_json(message)

    def get_online_count(self, client_type: str) -> int:
        """获取指定角色在线人数。"""
        if client_type == "driver":
            return len(self.active_drivers)
        elif client_type == "passenger":
            return len(self.active_passengers)
        return 0


manager = ConnectionManager()
