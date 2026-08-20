# 预鉴平台后端

FastAPI + SQLAlchemy 2 的可运行演示后端，覆盖预鉴 V5.1 的云端数据面、L1–L4 可审计推理、告警联动、确定性场景模拟，以及后续 Ubuntu 边缘网关可直接实现的 HTTP 契约。

## 能力

- 默认使用真实 SQLite 文件持久化；设置 `DATABASE_URL` 后可切换 PostgreSQL。
- 内置基于 HttpOnly Cookie 的登录会话，口令使用 PBKDF2-HMAC-SHA256 加盐存储，会话令牌仅以哈希形式落库。
- 启动时幂等写入 4 个模拟点位，主点位为“滨河路下穿隧道”。
- 13 个核心领域表：`users`、`auth_sessions`、`sites`、`devices`、`weather_snapshots`、`water_states`、`forecast_runs`、`forecast_points`、`alerts`、`inference_steps`、`action_records`、`audit_logs`、`scenario_runs`。
- L1–L4 推理步骤、规则/模型/DEM/标定版本和物理校验均可回看。
- 动作确认、边缘站拉取、设备回执和哈希链审计形成闭环。
- SSE 与 WebSocket 实时事件推送。
- 三个固定数据序列的确定性场景：快速积水、视觉降级、排水恢复。

## 本地运行

```powershell
cd D:\yujian-platform\server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

默认监听 `http://127.0.0.1:8000`，OpenAPI 文档位于 `/docs`。前端可使用短路径 `/api/...`；标准版本化路径为 `/api/v1/...`。

本地 `development`、`demo`、`test` 环境会幂等创建管理员：用户名 `admin`，本地默认口令 `Yujian@2026`，显示名“王海峰”。生产环境不会接受该内置默认口令；必须通过 `AUTH_SEED_ADMIN_PASSWORD` 设置独立强口令，并启用 `AUTH_SECURE_COOKIE=true`。首次登录后请尽快切换为组织自己的身份系统或凭据管理流程。

生产 PostgreSQL 示例：

```text
DATABASE_URL=postgresql+psycopg://yujian:password@127.0.0.1:5432/yujian
```

认证相关环境变量：`AUTH_SESSION_HOURS` 默认 12 小时，`AUTH_REMEMBER_DAYS` 默认 30 天，`AUTH_PBKDF2_ITERATIONS` 默认 310000；Cookie 名可用 `AUTH_COOKIE_NAME` 调整，跨站策略由 `AUTH_COOKIE_SAMESITE` 控制。

## 核心 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 用户名和口令登录，签发 HttpOnly 会话 Cookie |
| GET | `/api/v1/auth/me` | 读取当前登录用户 |
| POST | `/api/v1/auth/logout` | 撤销当前会话并清除 Cookie |
| GET | `/api/v1/health` | 数据库与种子状态 |
| GET | `/api/v1/dashboard` | 首页聚合数据 |
| GET | `/api/v1/sites` | 4 个点位及最新状态 |
| GET | `/api/v1/sites/{id}` | 点位、设备、历史水深和当前预测 |
| GET | `/api/v1/events` | 告警、动作与审计时间线 |
| GET | `/api/v1/reviews/{forecastRunId}` | L1–L4 推理复核详情 |
| GET | `/api/v1/devices` | 设备状态与边缘遥测 |
| GET | `/api/v1/audit` | 审计日志 |
| GET | `/api/v1/audit/verify` | 审计链完整性 |
| POST | `/api/v1/actions/{id}/confirm` | 人工确认联动 |
| POST | `/api/v1/actions/{id}/reject` | 人工驳回联动 |
| GET | `/api/v1/scenarios` | 场景目录 |
| POST | `/api/v1/scenarios/{key}/start` | 启动场景 |
| POST | `/api/v1/scenarios/runs/{id}/pause` | 暂停 |
| POST | `/api/v1/scenarios/runs/{id}/step` | 精确推进一个模拟分钟 |
| POST | `/api/v1/scenarios/runs/{id}/reset` | 清理场景数据并回到第 0 分钟 |
| GET | `/api/v1/events/stream` | SSE 实时流 |
| WS | `/api/v1/ws/live` | WebSocket 实时流 |

## Ubuntu 边缘契约

边缘端上行统一使用带事件时间、序列号和版本引用的信封。相同 `eventId` 的水状态补传会被幂等接收。

```json
{
  "eventId": "station-01-water-000019",
  "schemaVersion": 1,
  "eventType": "water.state",
  "tenantId": "demo-tenant",
  "siteId": "site-binh-rd-tunnel",
  "stationId": "station-binh-rd-tunnel",
  "deviceId": "dev-binh-rd-tunnel-camera",
  "eventTime": "2026-07-10T08:30:00+08:00",
  "sequenceNo": 19,
  "refs": {
    "demVersion": "dem-bh-20260701-v17",
    "calibrationVersion": "cal-bh-v9",
    "modelVersion": "reflection-v0.4.2"
  },
  "quality": {"score": 93, "status": "accepted", "flags": []},
  "payload": {
    "avgDepthCm": 15.4,
    "maxDepthCm": 25.1,
    "areaM2": 344.0,
    "volumeM3": 52.98,
    "depthSegmentsCm": [8.1, 16.8, 25.1, 19.0, 10.2],
    "slope1mCmMin": 0.72,
    "slope5mCmMin": 0.64,
    "slope10mCmMin": 0.58,
    "drainageSaturation": "red"
  }
}
```

边缘端流程：

1. `POST /api/v1/edge/v1/heartbeat` 上报心跳并取得期望配置。
2. `POST /api/v1/edge/v1/telemetry` 上传结构化状态；视频和点云未来走独立对象上传通道。
3. `GET /api/v1/edge/v1/stations/{stationId}/commands` 拉取已确认指令。
4. 执行本地车辆/安全回路联锁后，`POST /api/v1/edge/v1/commands/{actionId}/ack` 回执 `acked`、`verified` 或 `failed`。

## 测试

```powershell
pytest
```

测试使用临时 SQLite 数据库，不会污染演示库。
