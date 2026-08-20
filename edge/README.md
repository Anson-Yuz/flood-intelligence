# 预鉴 Ubuntu 边缘采集端

这是一个不依赖真实镭神 SDK 的可运行边缘端骨架。它用 mock LiDAR 和 mock 摄像头生成心跳、水状态、积水边界与 DEM 元数据；所有事件先写入 SQLite，再通过 HTTP 或 MQTT QoS 1 上报。真实硬件接入只需替换厂商适配器，平台事件协议无需改变。

当前实现不包含任何具体镭神型号、端口、数据包或私有协议假设，也不执行道闸等安全关键动作。

## 环境

- Ubuntu 22.04/24.04 或其他提供 Python 3.10+ 的 Linux
- HTTP/stdout 模式无第三方 Python 依赖
- MQTT 模式额外使用 `paho-mqtt`

## 快速运行

在本目录执行：

```bash
python3 -m yujian_edge --config config.example.json validate-config
python3 -m yujian_edge --config config.example.json once
python3 -m yujian_edge --config config.example.json run
```

`config.example.json` 默认使用 stdout，不需要服务器即可看到统一事件信封。

安装为命令行工具：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
yujian-edge --config config.example.json once
```

## HTTP 联调和断网补传

终端一启动本地接收器：

```bash
python3 scripts/mock_http_receiver.py --port 8080
```

终端二发送一组样例：

```bash
python3 -m yujian_edge --config config.http.example.json once
```

模拟断网时先停止接收器，再执行 `once`。命令会返回非零状态，但事件已经安全留在 SQLite。恢复接收器后执行：

```bash
python3 -m yujian_edge --config config.http.example.json queue-status
python3 -m yujian_edge --config config.http.example.json flush --json
```

服务端必须按 `eventId` 幂等去重：如果服务端已接收事件、边端却在删除本地记录前崩溃，恢复后会再次发送同一事件。

## MQTT

```bash
pip install -e '.[mqtt]'
python3 -m yujian_edge --config config.mqtt.example.json run
```

事件主题格式：

```text
yujian/v1/{tenantId}/{siteId}/{stationId}/events/{eventType}
```

HTTP POST 请求体和 MQTT 消息体是完全相同的 JSON 信封。MQTT 默认 QoS 1、不 retain；账号密码从配置指定的环境变量读取。

## 可用命令

```text
validate-config               校验配置
run                           常驻采集、心跳和补传
once [--no-dem]               采集一轮并退出
heartbeat                     立即上报心跳
sample                        立即上报水状态和边界
dem                           立即上报 DEM 元数据
queue-status                  查看 SQLite 待发队列
flush [--json]                强制补传
handle-command <file.json>    执行安全命令文件并上报 command ack
```

支持的命令类型仅有：

- `edge.collect.dem.v1`
- `edge.collect.water.v1`
- `edge.heartbeat.v1`
- `edge.flush.v1`

其他命令会被拒绝，尤其不会接受道闸、泵站或诱导屏等执行器控制。示例见 `examples/command-collect-water.json`。

## 事件类型

| 类型 | 内容 |
|---|---|
| `edge.heartbeat.v1` | 软件、设备适配器、运行模式、时钟与队列健康 |
| `water.state.v1` | 水深、面积、体积、上涨速率与 DEM 版本 |
| `water.boundary.v1` | 图像坐标系中的边界多边形、帧证据引用与标定版本 |
| `road.dem.metadata.v1` | DEM 版本、栅格、基准、精度、存储引用与哈希 |
| `edge.command.ack.v1` | 命令成功、拒绝或失败的可追溯回执 |

水状态和边界由同一次观测生成时共享同一个 `traceId`。所有事件具有持久化递增的 `sequence`，但云端排序仍应优先使用 `occurredAt` 并处理迟到数据。

## 配置

配置使用 JSON，避免边缘机额外安装 YAML 解析器。相对 `sqlitePath` 以配置文件所在目录为基准。生产 systemd 部署建议使用绝对路径 `/var/lib/yujian-edge/outbox.db`。

关键项：

- `identity`：租户、点位、站点和边缘节点身份。
- `transport.mode`：`stdout`、`http` 或 `mqtt`。
- `queue`：SQLite 路径、单批数量和指数退避范围。
- `runtime`：心跳、观测、DEM 与补传周期。
- `adapters.*.driver`：`mock` 或 `python`。
- `adapters.*.classPath`：真实实现的 `module.path:ClassName`。

## 接入真实硬件

真实 LiDAR 类继承 `LidarVendorAdapter`，真实摄像头/算法类继承 `CameraVendorAdapter`。配置示意：

```json
{
  "driver": "python",
  "classPath": "site_adapters.leishen:SiteLeishenAdapter",
  "options": {"sdkConfigPath": "/etc/yujian-edge/vendor-lidar.json"}
}
```

请根据实际采购型号取得镭神官方 Ubuntu SDK、头文件、动态库和示例程序后再实现 `SiteLeishenAdapter`。具体对接边界与上线检查见 `../docs/hardware-adapter.md`。

## 测试

```bash
python3 -m unittest discover -s tests -v
python3 scripts/selftest.py
```

自测覆盖统一信封、MQTT topic、HTTP POST、必需事件类型，以及“发送失败留队—恢复后补传”的核心路径。
