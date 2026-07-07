"""WebSocket 连接池管理模块。"""

from typing import Dict, List
from fastapi import WebSocket


class WebSocketPool:
    """管理 WebSocket 连接池，区分司机与乘客。"""

    def __init__(self):
        self.driver_connections: Dict[str, WebSocket] = {}
        self.passenger_connections: Dict[str, WebSocket] = {}

    async def connect_driver(self, driver_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.driver_connections[driver_id] = websocket

    async def connect_passenger(self, passenger_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.passenger_connections[passenger_id] = websocket

    def disconnect_driver(self, driver_id: str) -> None:
        self.driver_connections.pop(driver_id, None)

    def disconnect_passenger(self, passenger_id: str) -> None:
        self.passenger_connections.pop(passenger_id, None)

    def get_driver(self, driver_id: str) -> WebSocket:
        return self.driver_connections.get(driver_id)

    def get_passenger(self, passenger_id: str) -> WebSocket:
        return self.passenger_connections.get(passenger_id)

    def list_drivers(self) -> List[str]:
        return list(self.driver_connections.keys())

    def list_passengers(self) -> List[str]:
        return list(self.passenger_connections.keys())
