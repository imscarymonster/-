"""Pydantic 数据校验和传输对象定义。"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: Optional[str] = "passenger"


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    created_at: Optional[datetime]

    class Config:
        orm_mode = True


class StationBase(BaseModel):
    name: str
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None


class StationRead(StationBase):
    id: int

    class Config:
        orm_mode = True


class RouteBase(BaseModel):
    name: str
    origin_station_id: int
    destination_station_id: int
    description: Optional[str] = None


class RouteRead(RouteBase):
    id: int

    class Config:
        orm_mode = True


class DispatchLogBase(BaseModel):
    user_id: int
    route_id: int
    status: str
    notes: Optional[str] = None


class DispatchLogRead(DispatchLogBase):
    id: int
    created_at: Optional[datetime]

    class Config:
        orm_mode = True
