"""数据库与缓存连接配置模块。"""

import os
from typing import Optional

import redis
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 优先加载 .env 文件，使 os.getenv() 能直接读取其中的配置
_ENV_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
]
for _env_path in _ENV_CANDIDATES:
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        break


def _load_env_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """优先读取环境变量，若不存在则回退到手动解析 .env 文件（兼容未安装 dotenv 的场景）。"""
    env_value = os.getenv(key)
    if env_value:
        return env_value

    for env_path in _ENV_CANDIDATES:
        if not os.path.exists(env_path):
            continue
        with open(env_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                env_key, env_val = line.split("=", 1)
                if env_key.strip() == key:
                    return env_val.strip().strip('"').strip("'")

    return default


DATABASE_URL = _load_env_value(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/optibus"
)
REDIS_URL = _load_env_value("REDIS_URL", "redis://localhost:6379/0")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
redis_client = redis.Redis(connection_pool=redis_pool)


def get_db():
    """依赖注入：获取 SQLAlchemy 会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
