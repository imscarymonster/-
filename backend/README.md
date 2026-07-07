# Optibus Backend

这是 `optibus-project` 后端服务的基础脚手架，使用 FastAPI 作为 Web 框架。

## 目录结构

- `backend/app/`
  - `auth/`：用于登录与角色权限校验的空目录
  - `core/scheduler.py`：核心调度算法引擎的空函数结构
  - `database.py`：SQLAlchemy 与 Redis 连接配置
  - `models.py`：PostgreSQL ORM 模型定义
  - `schemas.py`：Pydantic 数据验证传输对象
  - `websocket_pool.py`：WebSocket 连接池管理，区分司机与乘客
  - `main.py`：FastAPI 入口文件，挂载基础路由

## 快速开始

1. 创建并激活 Python 虚拟环境
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 复制环境变量模板：
   ```bash
   cp .env.example .env
   ```
4. 启动应用：
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## 注意

本项目仅包含基础框架和文件注释，具体业务逻辑和权限实现需在后续开发中补充。
