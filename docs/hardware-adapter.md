# 镭神 LiDAR + 摄像头 Ubuntu 边缘适配说明

## 1. 设计边界

边缘端分为四层：

```text
镭神官方 SDK / V4L2 相机
            ↓
站点厂商适配器（只处理连接、解码、标定和健康）
            ↓
中立观测对象（DEM 元数据 / WaterObservation）
            ↓
统一事件信封 → SQLite outbox → HTTP 或 MQTT
```

平台只依赖中立事件，不依赖具体 LiDAR 型号、UDP 包、点字段或 SDK 类型。当前仓库没有真实设备信息，因此没有虚构型号、端口、扫描线数、驱动参数或协议。采购型号确定后，应以厂商随该型号提供的 Ubuntu SDK 和文档为唯一协议依据。

## 2. 厂商接口

接口位于 `edge/yujian_edge/adapters.py`。

### `LidarVendorAdapter`

真实类必须实现：

- `connect()`：加载厂商动态库、打开实际连接并完成必要初始化。
- `close()`：停止采集并释放 SDK 句柄。
- `health()`：返回连接、SDK 和设备健康；不得伪造在线状态。
- `capture_dem_metadata()`：触发/读取点云处理结果，返回 `DemMetadataObservation`。

`capture_dem_metadata()` 的 `storageRef` 指向已持久化 DEM 工件，`sha256` 是该工件真实内容哈希。不要把大体积点云或 GeoTIFF 直接塞进事件消息。

### `CameraVendorAdapter`

真实类必须实现：

- `connect()` / `close()`：管理 V4L2、GStreamer 或相机厂商 SDK 生命周期。
- `health()`：报告采集链路、分辨率、帧率和算法健康。
- `capture_water_observation()`：返回同一观测时刻的水状态和边界基础数据。

当前接口把“摄像头采集 + 候选雨滴反光算法”视为一个站点插件边界。工程化后可在插件内部继续拆分 frame source、boundary estimator 和 DEM fusion，但对平台仍输出相同 `WaterObservation`。

## 3. 真实镭神对接位置

建议在部署仓库或私有包中新建：

```text
site_adapters/
  __init__.py
  leishen.py       # SiteLeishenAdapter
  camera.py        # SiteCameraAdapter
```

配置：

```json
{
  "adapters": {
    "lidar": {
      "driver": "python",
      "classPath": "site_adapters.leishen:SiteLeishenAdapter",
      "options": {
        "sdkConfigPath": "/etc/yujian-edge/vendor-lidar.json",
        "demOutputDir": "/var/lib/yujian-edge/dem"
      }
    },
    "camera": {
      "driver": "python",
      "classPath": "site_adapters.camera:SiteCameraAdapter",
      "options": {
        "device": "/dev/video0",
        "calibrationPath": "/etc/yujian-edge/camera-calibration.json"
      }
    }
  }
}
```

`options` 只是站点插件自定义参数；核心运行时不会解释其中的 SDK 字段。

对接顺序：

1. 锁定实际采购型号、CPU 架构、Ubuntu 版本和厂商 SDK 版本。
2. 在隔离测试机跑通厂商官方示例，确认设备发现、时间戳和点云完整性。
3. 实现 `SiteLeishenAdapter`，把厂商对象转换为中立对象。
4. 将点云滤波、地面分割、配准和 DEM 生成工件放在站点插件或独立算法包。
5. 用真实 DEM 文件计算 SHA-256，保存标定版本和本地高程基准。
6. 用 mock/真实适配器对同一平台接收端做契约测试，确认事件字段不变。

不建议直接修改 `runtime.py` 调厂商 SDK；这样会把设备私有协议扩散到队列、HTTP 和平台侧。

## 4. 统一事件信封

HTTP 请求体与 MQTT 消息体完全一致：

| 字段 | 说明 |
|---|---|
| `schemaVersion` | 固定为 `yujian.edge.event/v1` |
| `eventId` | 全局唯一；云端幂等键 |
| `eventType` | 带版本的事件类型 |
| `occurredAt` | 设备/算法实际观测时间，UTC |
| `producedAt` | 信封生成时间，UTC |
| `sequence` | 该节点 SQLite 持久化递增序号 |
| `traceId` | 串联同帧水状态、边界、命令和后续审计 |
| `source` | 租户和边缘节点 |
| `subject` | 场地、站点和监测点 |
| `quality` | `status`、`confidence`、`reasons` |
| `context` | 配置、适配器、标定和 DEM 版本 |
| `payload` | 事件专属数据 |

示例位于 `edge/examples/`。`water.state.v1` 和 `water.boundary.v1` 在同一观测中共享 `traceId`，便于平台审计回放。

### HTTP

- 方法：`POST`
- Content-Type：`application/json`
- 成功：任意 2xx
- 附加头：`X-Yujian-Event-Id`、`X-Yujian-Event-Type`、`X-Yujian-Mqtt-Topic`
- Bearer token 仅从环境变量读取，不应写进 JSON 配置或日志。

### MQTT

```text
yujian/v1/{tenantId}/{siteId}/{stationId}/events/{eventType}
```

默认 QoS 1、非 retained。边端的 SQLite outbox 与 QoS 1 都提供 at-least-once 语义，因此云端仍必须按 `eventId` 去重。

建议未来命令主题为：

```text
yujian/v1/{tenantId}/{siteId}/{stationId}/commands/{commandType}
```

当前代码只通过 `handle-command` 验证安全命令契约，没有启动远程 MQTT 命令订阅。生产接入远程命令前必须增加设备证书、签名验证、防重放、短 TTL 和权限白名单。

## 5. 离线队列与补传

流程为“先入 SQLite，再尝试网络发送”：

1. 生成稳定 `eventId` 和持久化 `sequence`。
2. 使用 SQLite WAL 和 `synchronous=FULL` 写入 outbox。
3. HTTP 2xx 或 MQTT publish ack 后删除本地待发项。
4. 失败时保留原始 JSON，并按配置指数退避。
5. 进程启动和网络恢复后按创建时间补传。

这个设计不会静默丢弃事件，但可能重复投递。磁盘满属于需要告警的硬故障，生产应监控分区容量和 `outbox.pending`，并为 `/var/lib/yujian-edge` 设置合适容量及保留策略。

## 6. 命令安全边界

当前白名单只允许立即采集、心跳和补传：

- `edge.collect.dem.v1`
- `edge.collect.water.v1`
- `edge.heartbeat.v1`
- `edge.flush.v1`

命令必须匹配本机 `siteId`、`stationId`、`edgeNodeId`，且不得过期。执行结果通过 `edge.command.ack.v1` 上报。

道闸、泵站、广播和 LED 等执行器命令被刻意排除。这些动作需要独立安全控制器、人工授权、现场互锁和专项风险评估，不能复用采集 adapter 直接执行。

## 7. Ubuntu 部署注意事项

- 使用专用非登录用户 `yujian-edge`，只授予设备节点和数据目录所需权限。
- 相机权限通过受控 udev 规则或 `video` 组配置；不要用 root 常驻运行。
- 厂商 `.so` 放入受控只读目录，明确版本和校验值；使用 systemd 环境配置库路径。
- 配置 chrony/systemd-timesyncd，并把同步状态真实写入心跳，不能长期保持示例中的 `null`。
- HTTP/MQTT 生产环境启用 TLS 和双向身份认证；凭据从环境变量或设备密钥存储读取。
- 原始图像可能包含人脸和车牌，应优先边缘分析、最小化上传，并配置证据帧保留期限。
- 灯杆振动、相机外参变化、施工和极端天气后应触发重新标定或 DEM 复扫。

仓库内 `edge/deploy/yujian-edge.service` 是 systemd 起点。生产配置中的数据库路径应改为 `/var/lib/yujian-edge/outbox.db`，安装后再执行 `systemctl enable --now yujian-edge`。

## 8. 上线验收清单

- 官方示例与站点 adapter 都能连续运行，且没有虚构/默认型号参数。
- 设备时间、边端时间和平台时间偏差满足项目要求。
- 断网、重启、服务端 5xx、MQTT broker 重启后事件可补传。
- 平台按 `eventId` 去重，并可按 `traceId` 回放同次观测。
- DEM 工件可通过 `storageRef` 访问，SHA-256 与实际文件一致。
- 标定版本、配置版本、adapter 版本和 DEM 版本均进入事件。
- 磁盘满、SDK 断连、镜头异常和 DEM 失效均产生健康告警。
- 未经专项审批，采集进程无法向任何物理执行器发送动作。
