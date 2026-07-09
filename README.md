# -OptiBus：试验区动态摆渡车优化调度系统

## 1. 项目简介
本项目面向海南黎安试验区摆渡车用户与运营方，通过研发需求响应式动态调度系统，解决了传统固定模式下运力资源错配与候车体验差的问题，实现了摆渡车的柔性变线与智能高效调度。

## 2. 核心功能
- 乘客端：利用实时地理位置与数据流，为乘客提供候车时精准的车辆到站动态倒计时。
- 司机端：基于瞬时客流热力分布，在极短时间窗口内自动计算出最优车辆调度方案并直接反馈给摆渡车司机（不需要摆渡车司机主动请求），实现运力在不同线路间的智能转线与柔性互帮。
- 管理员端：给管理员提供全园区各线路的瞬时乘客数量、各摆渡车的实时位置及在途运力重构状态；在后台对车辆在线状态、司机排班及行驶日志进行管理；管理员可参考以上内容进行默认发车方式的调整。

## 3. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Vue 3 (Composition API) | `<script setup>` 语法，单文件组件 |
| 构建工具 | Vite 5 | 开发 HMR + 生产构建 |
| CSS | TailwindCSS 3 | 原子化 CSS + 响应式（`sm:`/`md:`/`lg:`/`xl:`） |
| 路由 | Vue Router 4 | 导航守卫实现角色权限控制 |
| HTTP | Axios | 组件内直接调用后端 API |
| 后端框架 | FastAPI | Python 异步 Web 框架，原生 WebSocket 支持 |
| 服务器 | Uvicorn | ASGI 服务器，127.0.0.1:8000 |
| ORM | SQLAlchemy 2.0 | PostgreSQL 驱动（当前仅健康检查用） |
| 缓存 | Redis 6+ | 全部实时数据存储（车辆位置、排队计数、调度状态） |
| 实时通信 | WebSocket | 司机调度指令下行推送 + TTS 触发 |
| 语音 | Web Speech API | 浏览器内置 TTS，`SpeechSynthesisUtterance`，中文播报 |
| 反向代理 | Nginx 1.18 | 静态文件托管 + /api /ws 代理 + SSL 终端 |
| 进程守护 | systemd | 后端开机自启 + 崩溃自动重启 |
| 部署 | 阿里云 ECS | Ubuntu 22.04，华南1（深圳），公网 47.107.104.57 |

## 4. 项目目录

```
OptiBus/
├── README.md
├── requirements.txt              # Python 后端依赖
├── .env                          # 环境变量（DATABASE_URL / REDIS_URL）
│
├── backend/
│   ├── main.py                   # 备用入口（指向 app.main）
│   └── app/
│       ├── main.py               # ★ 核心文件（~1700行）：ETA算法、调度引擎、
│       │                         #    发车模拟器、GPS转换、全部HTTP接口、WebSocket路由
│       ├── database.py           # SQLAlchemy + Redis 连接池配置
│       ├── schemas.py            # Pydantic 数据校验（DriverDailyCheckIn / LocationUpdate）
│       ├── models.py             # SQLAlchemy ORM 模型定义（User / Route / Station / DispatchLog）
│       ├── websocket.py          # WebSocket 连接管理器（ConnectionManager 类）
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py         # 路由骨架（占位）
│       ├── core/
│       │   └── scheduler.py      # 调度器骨架（占位）
│       └── models/
│           ├── __init__.py
│           └── bus_models.py     # 公交领域模型（占位）
│
├── frontend/
│   ├── index.html                # SPA 入口（含 viewport meta）
│   ├── package.json              # Vue3 / Vite5 / TailwindCSS3 / Axios
│   ├── vite.config.js            # 开发代理 /api → :8000, /ws → :8000
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.js               # Vue 应用入口
│       ├── App.vue               # 根组件
│       ├── style.css             # TailwindCSS 基础指令
│       ├── router/
│       │   └── index.js          # ★ 路由表 + 导航守卫（角色权限校验）
│       ├── components/
│       │   ├── MapCanvas.vue     # ★ SVG 园区路网（站点/线路/车辆/图例）
│       │   ├── Header.vue        # 公共头部（占位）
│       │   ├── BusIcon.vue       # 车辆图标（占位）
│       │   └── StationCircle.vue # 站点圆圈（占位）
│       ├── views/
│       │   ├── PassengerView.vue # ★ 乘客端：站点选择 → ETA 倒计时
│       │   ├── DriverView.vue    # ★ 司机端：GPS + WebSocket + TTS + 模拟行驶
│       │   ├── AdminView.vue     # ★ 管理端：监控看板 + 排班 + 运力预警
│       │   ├── LoginView.vue     # 统一登录页
│       │   └── HomeView.vue      # 首页入口（占位）
│       ├── api/
│       │   ├── index.js          # API 封装（占位）
│       │   ├── request.js        # Axios 实例（占位）
│       │   └── busService.js     # 车辆服务（占位）
│       ├── store/
│       │   └── bus.js            # Pinia 状态（占位）
│       └── utils/
│           ├── websocket.js      # WebSocket 客户端（占位）
│           └── tts.js            # TTS 播报工具（占位）
│
├── database/
│   └── seed_data.json            # 初始种子数据
│
└── docs/
    ├── SystemArchitecture.md      # 系统架构文档（初稿）
    └── VibeLogs/
        └── vibe_log_01.md        # 项目迭代日志（空）
```

> 标注"占位"的文件为预留模块骨架，实际业务逻辑集中在打 ★ 的核心文件中。

## 5. 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.10+ |
| Node.js | 18.0+ |
| Redis | 6.0+ |
| Nginx | 1.18+ |
| 操作系统 | Ubuntu 22.04（服务器）/ Windows 10+（开发） |

## 6. 安装与启动

### 本地开发

```bash
# 1. 安装 Python 依赖
cd backend
pip install -r ../requirements.txt

# 2. 启动 Redis（本地需安装）
redis-server

# 3. 启动后端
$env:PYTHONIOENCODING="utf-8"           # Windows PowerShell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 安装前端依赖并启动
cd ../frontend
npm install
npm run dev                             # http://localhost:5173
```

### 生产部署（阿里云）

```bash
# 1. 安装系统依赖
apt-get install nginx redis-server python3-pip nodejs

# 2. 上传代码到 /opt/optibus/

# 3. 构建前端
cd /opt/optibus/frontend && npm install && npm run build

# 4. 配置 Nginx：静态文件 + /api /ws 反向代理

# 5. 启动后端（systemd 守护）
systemctl enable --now optibus
```

## 7. 演示账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | `admin` | `123456` |
| 司机 | `driver01` | `123456` |
| 乘客 | 无需登录 | — |

## 8. 核心接口

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/buses/locations` | 全网车辆实时拓扑位置 |
| GET | `/api/eta/{station}?route=line1_cw` | 站点 ETA 查询 |
| POST | `/api/dispatch/passenger_action` | 乘客加入/离开排队 |
| POST | `/api/buses/location/update` | 司机 GPS 坐标上报 |
| POST | `/api/driver/sign_off` | 司机签退 |
| GET | `/api/dispatch/dashboard` | 管理端看板数据 |
| GET | `/api/dispatch/stats` | 各线路排队人数 |
| POST | `/api/dispatch/reset_line1` | 重置 1 号线 |
| WS | `/ws/driver/{driver_id}` | 司机调度推送 |

全部 17 个端点详见代码 `backend/app/main.py`。

## 9. 配置与密钥说明

项目使用 `.env` 文件存储敏感配置（不提交 Git）：

```bash
# backend/.env
DATABASE_URL=postgresql://user:password@localhost:5432/optibus
REDIS_URL=redis://localhost:6379/0
```

Redis 连接串使用本地实例。PostgreSQL 非必须——核心功能全部走 Redis，PostgreSQL 离线不影响运行。

## 10. 常见问题

| 问题 | 解决方法 |
|------|---------|
| `ECONNREFUSED :8000` | 后端未启动：`systemctl start optibus` 或手动 `uvicorn` |
| Redis `TimeoutError` | 检查 Redis 是否运行：`redis-cli ping` |
| 手机 GPS 不弹授权 | HTTP 下浏览器拒绝 GPS API，需 HTTPS：`https://47.107.104.57` |
| 自签证书浏览器警告 | 点「高级」→「继续前往」即可（iOS Safari 除外） |
| `npm install` 权限错误 | Windows：`npm config set cache C:/Users/xxx/AppData/Local/npm-cache` |
| `UnicodeEncodeError` | Windows 终端 GBK 编码问题：`$env:PYTHONIOENCODING="utf-8"` |
| 车辆在地图上走空白 | 前端已修复为 SVG 原生路径插值，需刷新浏览器（Ctrl+Shift+R） |

## 11. 已知限制

1. **Mock 认证**：账号密码前端硬编码，后端无鉴权中间件
2. **Redis 无持久化**：重启丢失全部实时数据（车辆位置、排队记录）
3. **GPS 参考点近似**：`GPS_REF_LAT/LNG` 需实地校准才能精确定位
4. **路线硬编码**：站点坐标和线路序列写在源码中，新园区需改代码
5. **自签 SSL 证书**：生产需域名 + Let's Encrypt CA 证书
6. **调度引擎**：基于固定阈值（13 人/车 + 5 安全余量），未引入历史数据预测

## 12. 团队成员

- **陈泽宇**（2024213810）：产品设计与提示词，系统需求拆解，机制设计提示词，Vibe 日志，项目总文件编辑，前后端统一
- **江沛祺**（2024213732）：前端开发，Vibe Coding 提示词
- **胡正轩**（2024213778）：后端开发，Vibe Coding 提示词
