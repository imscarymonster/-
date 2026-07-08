"""Pydantic 数据校验和传输对象定义。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OptiBusBaseModel(BaseModel):
    """为所有响应模型提供 ORM 兼容配置。"""

    if ConfigDict is not None:
        model_config = ConfigDict(from_attributes=True)
    else:
        class Config:
            orm_mode = True


class UserBase(BaseModel):
    username: str
    role: Optional[str] = "passenger"
    status: Optional[str] = "active"


class UserRead(UserBase, OptiBusBaseModel):
    id: int


class RouteBase(BaseModel):
    route_name: str
    default_bus_count: int = 1


class RouteRead(RouteBase, OptiBusBaseModel):
    id: int


class StationBase(BaseModel):
    route_id: int
    station_name: str
    sequence: int = 1
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class StationRead(StationBase, OptiBusBaseModel):
    id: int


class DispatchLogBase(BaseModel):
    bus_id: int
    from_route_id: int
    to_route_id: int
    trigger_time: Optional[datetime] = None
    complete_time: Optional[datetime] = None


class DispatchLogRead(DispatchLogBase, OptiBusBaseModel):
    id: int


class DriverDailyCheckIn(BaseModel):
    """司机每日发车打卡。"""

    driver_id: int
    route_id: int


class LocationUpdate(BaseModel):
    """司机高频坐标上报。"""

    lat: float
    lng: float
