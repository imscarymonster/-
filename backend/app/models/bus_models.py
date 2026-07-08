# 数据库 ORM 模型
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Route(Base):
    """线路"""
    __tablename__ = "routes"
    id       = Column(Integer, primary_key=True, autoincrement=True)
    name     = Column(String(64), nullable=False)
    color    = Column(String(16), default="#3388FF")
    status   = Column(Integer, default=1)
    stations = relationship("Station", back_populates="route")


class Station(Base):
    """站点"""
    __tablename__ = "stations"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    route_id  = Column(Integer, ForeignKey("routes.id"))
    name      = Column(String(64), nullable=False)
    latitude  = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    seq_order = Column(Integer, default=0)
    route     = relationship("Route", back_populates="stations")


class Bus(Base):
    """车辆"""
    __tablename__ = "buses"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    plate     = Column(String(16), unique=True, nullable=False)
    route_id  = Column(Integer, ForeignKey("routes.id"))
    latitude  = Column(Float)
    longitude = Column(Float)
    status    = Column(Integer, default=0)  # 0=离线,1=在线,2=行驶中,3=变线中
    driver_id = Column(Integer, ForeignKey("drivers.id"))


class Driver(Base):
    """司机"""
    __tablename__ = "drivers"
    id     = Column(Integer, primary_key=True, autoincrement=True)
    name   = Column(String(32), nullable=False)
    phone  = Column(String(16))
    status = Column(Integer, default=0)


class TripLog(Base):
    """行驶日志"""
    __tablename__ = "trip_logs"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    bus_id          = Column(Integer, ForeignKey("buses.id"))
    driver_id       = Column(Integer, ForeignKey("drivers.id"))
    route_id        = Column(Integer, ForeignKey("routes.id"))
    start_time      = Column(DateTime)
    end_time        = Column(DateTime)
    mileage         = Column(Float, default=0)
    passenger_count = Column(Integer, default=0)


class WaitRecord(Base):
    """候车记录"""
    __tablename__ = "wait_records"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    station_id  = Column(Integer, ForeignKey("stations.id"))
    user_id     = Column(String(64))
    wait_seconds = Column(Integer, nullable=False)
    recorded_at = Column(DateTime)
