"""OptiBus 系统 ORM 模型定义。"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    role = Column(String(50), nullable=False, default="passenger")
    status = Column(String(50), nullable=False, default="active")


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    route_name = Column(String(255), nullable=False, index=True)
    default_bus_count = Column(Integer, nullable=False, default=1)

    stations = relationship("Station", back_populates="route", cascade="all, delete-orphan")
    from_dispatch_logs = relationship(
        "DispatchLog",
        foreign_keys="DispatchLog.from_route_id",
        back_populates="from_route",
        cascade="all, delete-orphan",
    )
    to_dispatch_logs = relationship(
        "DispatchLog",
        foreign_keys="DispatchLog.to_route_id",
        back_populates="to_route",
        cascade="all, delete-orphan",
    )


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False, index=True)
    station_name = Column(String(255), nullable=False)
    sequence = Column(Integer, nullable=False, default=1)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    route = relationship("Route", back_populates="stations")


class DispatchLog(Base):
    __tablename__ = "dispatch_logs"

    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(Integer, nullable=False, index=True)
    from_route_id = Column(Integer, ForeignKey("routes.id"), nullable=False, index=True)
    to_route_id = Column(Integer, ForeignKey("routes.id"), nullable=False, index=True)
    trigger_time = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    complete_time = Column(DateTime, nullable=True)

    from_route = relationship("Route", foreign_keys=[from_route_id], back_populates="from_dispatch_logs")
    to_route = relationship("Route", foreign_keys=[to_route_id], back_populates="to_dispatch_logs")
