-- OptiBus 数据库初始化脚本
-- 试验区动态摆渡车优化调度系统

-- 线路表
CREATE TABLE IF NOT EXISTS routes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(64)  NOT NULL COMMENT '线路名称',
    color       VARCHAR(16)  DEFAULT '#3388FF' COMMENT '线路标识颜色',
    status      TINYINT      DEFAULT 1 COMMENT '状态: 1=启用, 0=停用',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- 站点表
CREATE TABLE IF NOT EXISTS stations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id    INTEGER      NOT NULL COMMENT '所属线路',
    name        VARCHAR(64)  NOT NULL COMMENT '站点名称',
    latitude    DOUBLE       NOT NULL COMMENT '纬度',
    longitude   DOUBLE       NOT NULL COMMENT '经度',
    seq_order   INTEGER      DEFAULT 0 COMMENT '在线路中的顺序',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);

-- 车辆表
CREATE TABLE IF NOT EXISTS buses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plate       VARCHAR(16)  NOT NULL UNIQUE COMMENT '车牌号',
    route_id    INTEGER      COMMENT '当前所属线路',
    latitude    DOUBLE       COMMENT '实时纬度',
    longitude   DOUBLE       COMMENT '实时经度',
    status      TINYINT      DEFAULT 0 COMMENT '状态: 0=离线, 1=在线, 2=行驶中, 3=变线中',
    driver_id   INTEGER      COMMENT '当前司机',
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);

-- 司机表
CREATE TABLE IF NOT EXISTS drivers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(32)  NOT NULL COMMENT '姓名',
    phone       VARCHAR(16)  COMMENT '手机号',
    status      TINYINT      DEFAULT 0 COMMENT '状态: 0=离线, 1=在线, 2=出车中',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- 行驶日志表
CREATE TABLE IF NOT EXISTS trip_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bus_id      INTEGER      NOT NULL,
    driver_id   INTEGER      NOT NULL,
    route_id    INTEGER      NOT NULL COMMENT '实际行驶线路',
    start_time  DATETIME     NOT NULL,
    end_time    DATETIME,
    mileage     DOUBLE       DEFAULT 0 COMMENT '行驶里程(km)',
    passenger_count INTEGER  DEFAULT 0 COMMENT '载客数',
    FOREIGN KEY (bus_id)    REFERENCES buses(id),
    FOREIGN KEY (driver_id) REFERENCES drivers(id),
    FOREIGN KEY (route_id)  REFERENCES routes(id)
);

-- 候车记录表（用于效能统计）
CREATE TABLE IF NOT EXISTS wait_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id  INTEGER      NOT NULL,
    user_id     VARCHAR(64)  COMMENT '匿名用户标识',
    wait_seconds INTEGER     NOT NULL COMMENT '候车时长(秒)',
    recorded_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id) REFERENCES stations(id)
);
