# WebSocket 网关 — 处理三端实时通信
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # client_type -> {client_id: websocket}
        self.connections: Dict[str, Dict[str, WebSocket]] = {
            "passenger": {},
            "driver": {},
            "admin": {},
        }

    async def connect(self, websocket: WebSocket, client_type: str, client_id: str):
        await websocket.accept()
        self.connections[client_type][client_id] = websocket

    def disconnect(self, client_type: str, client_id: str):
        self.connections[client_type].pop(client_id, None)

    async def send_to_type(self, client_type: str, message: dict):
        """向某类客户端广播消息"""
        for ws in self.connections.get(client_type, {}).values():
            await ws.send_json(message)

    async def send_personal(self, client_type: str, client_id: str, message: dict):
        """向指定客户端发送消息"""
        ws = self.connections.get(client_type, {}).get(client_id)
        if ws:
            await ws.send_json(message)

    def get_online_count(self, client_type: str) -> int:
        return len(self.connections.get(client_type, {}))


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_type: str, client_id: str = "anonymous"):
    """WebSocket 端点处理函数"""
    await manager.connect(websocket, client_type, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            # 根据消息类型处理业务逻辑
            msg_type = data.get("type")
            if msg_type == "location_update":
                # 车辆位置更新 → 广播给所有乘客和管理员
                await manager.send_to_type("passenger", data)
                await manager.send_to_type("admin", data)
            elif msg_type == "dispatch":
                # 调度指令 → 发送给指定司机
                target_id = data.get("driver_id")
                await manager.send_personal("driver", target_id, data)
    except WebSocketDisconnect:
        manager.disconnect(client_type, client_id)
