# 预鉴（豫见汛情）

城市道路积水预报与路面状况监测平台。本仓库是项目需求、设计、代码、测试与协作记录的统一工程锚点，也是面向竞赛评审与本地联调的可运行原型。

预鉴面向城市低洼道路、下穿隧道和地下空间入口，展示“边端感知—云端可审计推理—分级预警—人工处置—履职留痕”的完整产品形态，并附带 DEM 路面变化和养护优先级视图。当前产品路径优先聚焦汛期积水预报预警，后续再延伸道路养护能力。

> **演示与安全边界：** 当前仓库是竞赛原型与工程骨架，不是已通过政府采购验收的生产系统。深圳地图底图和辖区场景照片来自公开真实资料，但照片不是实时监控画面；水深、趋势、算法精度、设备状态、养护金额和联动结果统一标识为“模拟态势 · 待接入实测”。雨滴反光算法仍需真实降雨数据验证；道闸动作仅为模拟建议，不连接真实执行器。任何生产下控都必须在真实硬件、联锁、权限、审计和专项安全验收完成后启用。

## 在线公开演示

- 地址：<https://songtaoluo007-maker.github.io/yujian-flood-intelligence/>
- 直接点击“进入访客演示”，无需账号密码。
- GitHub Pages 版本仅部署静态前端，所有业务数据与处置动作均为浏览器内模拟，不连接后端、数据库、摄像头、LiDAR 或真实执行器。
- 公开站点由 `gh-pages` 分支承载构建产物；后续源代码更新需重新构建并发布该分支。
- 页面支持桌面、平板与移动端任务优先重排：1366px 紧凑侧栏、1024px 单列工作区、768px 以下底部导航。
- 源代码公开仅用于浏览、学习、竞赛评审与非商业评估；复用边界见 [`LICENSE`](LICENSE)。

## 当前阶段

`Phase 1.3 — 公开响应式演示`

- Web、FastAPI、数据库认证、Ubuntu edge 骨架、启动脚本和演示文档的软件链路已经完成。
- 风险总览已接入深圳 OpenStreetMap 主底图、CARTO 备用底图与十个区/新区的真实公开场景照片；在线瓦片均不可用时会降级到本地简化背景，地区切换仍会联动地图点位、照片和风险态势。
- 态势指标使用明确标识的确定性模拟数据，可复位、可重放、可审计；真实照片统一标注“辖区实景 · 非实时监控”。
- 登录采用数据库用户与服务端会话；红色、黄色预警会分别触发全页红/黄边框光晕。
- 产品基线为《预鉴 V5.1》；历史 DOCX 与 V4.7 PDF 仅作追溯参考。
- 镭神 LiDAR 的真实型号、SDK、硬件协议和现场 E1+ 验证仍待接入。

## 协作入口与唯一事实源

GitHub 仓库中的 Issue、ADR、代码、测试和 `PROJECT_LEDGER.md` 是项目唯一事实源。聊天记录、本地便笺和自动化报告不能替代正式工程记录。

开始任务前依次阅读：

1. [`PROJECT_LEDGER.md`](PROJECT_LEDGER.md)：当前状态、用户优化要求、工作记录和交接；
2. [`AGENTS.md`](AGENTS.md)：AI 协作入口；
3. 关联 GitHub Issue、ADR 和 PR；
4. 对应角色的任务说明。

### 协作角色

| 角色 | 主要职责 | 工作入口 |
|---|---|---|
| 人类项目负责人 | 确认目标、优先级、风险接受与最终合并 | Issue、PR、`PROJECT_LEDGER.md` |
| Codex | Issue 范围内的代码实现与测试 | [`CODEX.md`](CODEX.md) |
| Claude | 需求、架构、风险、测试覆盖和代码变更审查 | [`CLAUDE.md`](CLAUDE.md) |
| OpenClaw | 自动化运行、状态汇总、测试调度、报告和异常提醒 | [`OPENCLAW.md`](OPENCLAW.md) |
| ChatGPT 顾问 | 产品澄清、方案讨论和跨角色协调建议 | `PROJECT_LEDGER.md` 与关联 Issue |

### 基本工作流

```text
用户要求或问题
→ 登记 PROJECT_LEDGER.md
→ 创建或更新 Issue
→ 确认变更等级，必要时建立 ADR
→ 建立分支并实施
→ 测试与审查
→ PR
→ 更新账本和交接
→ 人类确认
```

### 协作规则

- 同一核心模块尽量只由一个任务分支修改；发现范围重叠时先登记并协调顺序。
- 用户新增优化要求先登记 `OPT` 编号，再决定进入当前任务或后续计划。
- 配准、DEM、水深、趋势、置信度、数据契约等 C3 变更必须有 ADR、回放、边界测试和多方审查。
- 每次交接都要写明做了什么、为什么、修改文件、验证结果、未完成项、风险和下一步。
- 自动化报告和 AI 审查不能替代项目负责人的最终确认。

详细规则见 [`GOVERNANCE/CHANGE_LEVELS.md`](GOVERNANCE/CHANGE_LEVELS.md) 和 [`docs/coordination/COLLABORATION_PROTOCOL.md`](docs/coordination/COLLABORATION_PROTOCOL.md)。

## 材料索引

| 材料 | 用途 | 状态 |
|---|---|---|
| 《预鉴 V5.1》 | 当前唯一产品基线 | 生效 |
| [`PROJECT_LEDGER.md`](PROJECT_LEDGER.md) | 项目快照、用户要求、工作记录与交接 | 开工必读、收工必写 |
| GitHub Issue #1 | Phase 1 挑战杯完整平台的实施与验收 | 已完成软件原型 |
| GitHub Issue #3 | 深圳真实地图/实景、登录认证与预警光晕增强 | 已完成实现，待 PR 人工确认 |
| [`ADR-0001`](docs/adr/0001-edge-cloud-flood-intelligence-contract.md) | 云边协同数据契约与自动联动安全边界 | Proposed，待 PR 人工/多方审查 |
| [`docs/architecture.md`](docs/architecture.md) | 系统架构与部署说明 | 当前实现 |
| [`docs/hardware-adapter.md`](docs/hardware-adapter.md) | Ubuntu、镭神与真实硬件接入边界 | 待真实型号/SDK补全 |
| [`docs/demo-script.md`](docs/demo-script.md) | 五分钟挑战杯演示、复位和故障兜底 | 可执行 |
| [`server/README.md`](server/README.md) | FastAPI、数据库、接口与 edge 契约 | 可执行 |
| [`edge/README.md`](edge/README.md) | Ubuntu edge、adapter、outbox 与传输 | 可执行骨架 |
| 历史 DOCX 与 V4.7 PDF | 需求沿革追溯 | 非当前基线 |

## 当前可演示能力

- React/Vite 可视化原型：登录、深圳十区实景风险总览、事件指挥、推理审计、设备管理、积水模拟与养护决策。
- 深圳态势视图：OpenStreetMap 主底图、CARTO 备用底图、本地简化背景三级降级，十个区/新区的真实公开场景照片、地区联动切换、风险点位与队列联动，以及红/黄全页预警光晕。
- FastAPI 后端：数据库用户、哈希密码、服务端会话登录/注销，以及 4 个确定性种子点位、L1–L4 推理记录、告警与动作、哈希链审计、SSE/WebSocket 和场景模拟器。
- Ubuntu 边缘骨架：镭神 LiDAR/摄像头厂商适配接口、统一事件信封、HTTP/MQTT、SQLite 断网队列和补传。
- 两种运行方式：Windows 本地一键启动，或 Docker Compose 启动前端、FastAPI 和 PostgreSQL。

前端展示主体读取 [`src/data/demoData.js`](src/data/demoData.js) 中明确标识的确定性模拟夹具；地图与照片是真实公开资料，水深、预测、告警和处置指标仍为模拟数据。预警发布、人工复核、证据读取、平台快照和登录会话已接入 FastAPI，服务不可用时业务展示才回退到前端 mock。两者共同保证路演稳定，并为后续全面切换实时 API 保留边界。

地图优先使用 OpenStreetMap 标准瓦片，连续加载失败后自动切换 CARTO Positron；两个在线源均失败时显示本地简化背景，并保留风险点位与实景切换能力。在线地图均保留可见署名，十张辖区场景照片的原始页面、作者与许可证记录在 [`docs/assets/shenzhen-scene-sources.md`](docs/assets/shenzhen-scene-sources.md)。公开瓦片服务没有生产 SLA，正式部署应根据访问规模评估自建或采购合规地图服务。

## Windows 一键启动

需要 Node.js 20+ 和 Python 3.10+。首次运行会自动创建 `server/.venv` 并安装依赖。

```powershell
Copy-Item .env.example .env
PowerShell -ExecutionPolicy Bypass -File .\start-demo.ps1
```

启动完成后：

- 前端：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- FastAPI：[http://127.0.0.1:8000](http://127.0.0.1:8000)
- OpenAPI：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 健康检查：[http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

本地开发首次启动会创建默认管理员：

- 用户名：`admin`
- 密码：`Yujian@2026`

该账号仅用于本地开发和评审联调。生产部署必须通过环境变量设置独立强密码、启用 HTTPS，并将认证 Cookie 配置为 Secure；不得沿用仓库默认口令。

操作端 REST、UI 兼容接口、SSE 与 WebSocket 均要求有效人员会话；健康检查和 /edge/v1 暂作为独立设备信任域保持公开。将 Ubuntu/镭神链路暴露到可信局域网之外前，必须补充设备密钥、签名或 mTLS。

停止由脚本启动的进程：

```powershell
.\stop-demo.ps1
```

脚本只停止 `.demo/processes.json` 中记录且启动时间一致的进程，不会按端口盲目结束其他程序。日志位于 `.demo/logs/`。

常用选项：

```powershell
.\start-demo.ps1 -Install
.\start-demo.ps1 -NoBrowser
.\start-demo.ps1 -FrontendPort 5174 -BackendPort 8001
```

## Docker Compose

Docker 模式包含 PostgreSQL 16、FastAPI 和 Vite。首次启动需要拉取镜像并安装容器内依赖，耗时会更长。

```powershell
Copy-Item .env.example .env
.\start-demo.ps1 -Docker
docker compose ps
```

停止但保留 PostgreSQL 数据：

```powershell
.\stop-demo.ps1 -Docker
```

只有明确需要清空演示数据库时才运行 `docker compose down -v`。

## 手动开发

前端：

```powershell
npm ci
npm run dev
```

后端：

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

后端默认使用 `server/yujian.db`；设置 `DATABASE_URL` 后可切换 PostgreSQL。数据库启动时会幂等迁移认证字段、创建会话表，并写入确定性模拟数据。

边缘 mock：

```powershell
cd edge
python -m yujian_edge --config config.example.json once
python -m unittest discover -s tests -v
```

## 核心接口

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/health` | 数据库、版本和种子状态 |
| POST | `/api/v1/auth/login` | 校验数据库用户并创建 HttpOnly 会话 Cookie |
| GET | /api/v1/auth/session | 无噪声读取当前会话状态 |
| GET | /api/v1/auth/me | 读取当前登录用户 |
| POST | `/api/v1/auth/logout` | 撤销当前服务端会话并清除 Cookie |
| GET | `/api/v1/dashboard` | 首页聚合数据 |
| GET | `/api/v1/sites` | 监测点和最新状态 |
| GET | `/api/v1/events` | 告警、动作与审计时间线 |
| GET | `/api/v1/reviews/{forecastRunId}` | L1–L4 推理复核 |
| GET | `/api/v1/audit/verify` | 校验审计哈希链 |
| POST | `/api/v1/actions/{id}/confirm` | 人工确认建议动作 |
| POST | `/api/v1/actions/{id}/reject` | 人工驳回建议动作 |
| GET/POST | `/api/v1/scenarios...` | 确定性模拟场景 |
| POST | `/api/v1/edge/v1/telemetry` | 接收统一 edge 信封及旧版扁平信封 |
| GET | `/api/v1/events/stream` | SSE 实时事件 |
| WS | `/api/v1/ws/live` | WebSocket 实时事件 |
| GET | `/api/snapshot` | 前端演示平台快照 |
| GET | `/api/events/{eventId}/evidence` | 读取持久化证据摘要 |
| POST | `/api/events/{eventId}/publish` | 确认动作并记录渠道回执 |
| POST | `/api/events/{eventId}/manual-review` | 驳回动作并进入人工复核队列 |

完整接口见 FastAPI `/docs` 和 [`server/README.md`](server/README.md)。

## Ubuntu 镭神边缘架构

边缘节点运行于 Ubuntu，LiDAR 平时间歇扫描形成 DEM，摄像头在降雨时输出候选积水边界。厂商 SDK 被隔离在 `LidarVendorAdapter`/`CameraVendorAdapter` 后，事件先进入 SQLite outbox，再通过 HTTP 或 MQTT QoS 1 上报；断网恢复后按原 `eventId` 补传。

后端 `/api/v1/edge/v1/telemetry` 已原生兼容边缘端嵌套 `yujian.edge.event/v1`，并继续接收早期扁平信封。服务端保留显式适配/归一化层：`water.state.v1` 转换为内部水状态领域事件，心跳、边界、DEM 元数据和命令回执按各自语义处理；原始 `eventId`、`traceId`、事件时间、质量和版本引用继续用于幂等与审计。该适配层是后续协议版本演进的稳定边界。

直接联调时，将 edge HTTP 配置的 endpoint 指向 `http://127.0.0.1:8000/api/v1/edge/v1/telemetry`，并把 `tenantId`、`siteId`、`stationId` 配置为后端已注册身份；仓库内 HTTP 示例默认指向 8080 mock receiver，不能原样当作云端地址。

详见：

- [边缘运行说明](edge/README.md)
- [硬件适配说明](docs/hardware-adapter.md)
- [系统架构](docs/architecture.md)

## 项目结构

```text
yujian-platform/
├─ src/                    React 可视化原型
├─ public/                 静态资源与深圳辖区实景照片
├─ server/                 FastAPI、SQLAlchemy、推理与场景模拟
├─ edge/                   Ubuntu mock adapter 与离线 outbox
├─ docs/                   架构、硬件对接和五分钟演示脚本
├─ design/                 选定的视觉参考
├─ docker-compose.yml      PostgreSQL + FastAPI + Vite
├─ start-demo.ps1          Windows 一键启动
└─ stop-demo.ps1           安全停止已跟踪进程
```

## 演示

五分钟路演顺序、场景复位方法、答辩备用 API 和故障兜底见 [`docs/demo-script.md`](docs/demo-script.md)。

## 验证

```powershell
npm run build

cd server
pytest

cd ..\edge
python -m unittest discover -s tests -v
python scripts/selftest.py
```
