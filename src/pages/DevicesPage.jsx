import { useMemo, useState } from "react";
import {
  ArrowClockwise,
  BatteryCharging,
  Camera,
  CheckCircle,
  CloudRain,
  Cpu,
  Funnel,
  HardDrives,
  Lightning,
  MagnifyingGlass,
  Pulse,
  Warning,
  WifiHigh,
  Wrench,
  XCircle,
} from "@phosphor-icons/react";
import { devicesData, filterOptions } from "../data/demoData";

function statusTone(status) {
  if (status === "online") return "success";
  if (status === "degraded") return "warning";
  return "critical";
}

export function DevicesPage() {
  const [devices, setDevices] = useState(devicesData);
  const [selectedId, setSelectedId] = useState(devicesData[0].id);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("全部状态");
  const [mode, setMode] = useState("全部模式");
  const [notice, setNotice] = useState("设备状态每30秒自动刷新，离线站点已启用边端缓存。 ");

  const filteredDevices = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return devices.filter((device) => {
      const matchesQuery =
        !normalized ||
        device.id.toLowerCase().includes(normalized) ||
        device.siteName.toLowerCase().includes(normalized);
      const matchesStatus = status === "全部状态" || device.statusLabel === status;
      const matchesMode = mode === "全部模式" || device.mode === mode;
      return matchesQuery && matchesStatus && matchesMode;
    });
  }, [devices, query, status, mode]);

  const activeDevice = devices.find((item) => item.id === selectedId) ?? filteredDevices[0] ?? devices[0];
  const onlineCount = devices.filter((item) => item.status === "online").length;
  const degradedCount = devices.filter((item) => item.status === "degraded").length;
  const offlineCount = devices.filter((item) => item.status === "offline").length;

  const updateDevice = (updater) => {
    setDevices((current) => current.map((item) => (item.id === activeDevice.id ? updater(item) : item)));
  };

  const runSelfCheck = () => {
    if (activeDevice.status === "offline") {
      setNotice(`${activeDevice.id} 无法建立远程连接，已生成现场检修工单草稿。`);
      return;
    }
    const warning = activeDevice.demAge > 30 ? "发现DEM基线超过30天，建议晴天补扫。" : "相机、供电、通信与边端算法均通过。";
    setNotice(`${activeDevice.id} 自检完成：${warning}`);
  };

  const switchMode = () => {
    if (activeDevice.status === "offline") {
      setNotice(`${activeDevice.id} 当前离线，模式切换指令已进入待发送队列。`);
      return;
    }
    const nextMode = activeDevice.mode === "平时模式" ? "降雨模式" : "平时模式";
    updateDevice((item) => ({
      ...item,
      mode: nextMode,
      lidar: nextMode === "平时模式" ? "定时待命" : "待机",
      camera: nextMode === "平时模式" ? "待机" : "工作中 · 30fps",
    }));
    setNotice(`${activeDevice.id} 已切换至${nextMode}。`);
  };

  const triggerScan = () => {
    if (activeDevice.status === "offline") {
      setNotice(`${activeDevice.id} 离线，无法触发扫描。`);
      return;
    }
    updateDevice((item) => ({ ...item, mode: "平时模式", lidar: "扫描任务已排队" }));
    setNotice(`${activeDevice.id} 已创建DEM补扫任务，将在降雨结束且路面干燥后执行。`);
  };

  return (
    <div className="subpage devices-page" data-page="devices">
      <header className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow">
            <HardDrives size={16} weight="fill" />
            设备运维
          </div>
          <h1>边端站点管理</h1>
          <p>监控路灯杆设备的供电、通信、传感器模式与数据质量。</p>
        </div>
        <div className="page-header-actions">
          <span className="demo-data-badge">6 台演示设备</span>
          <button className="button button-secondary" type="button" onClick={() => setNotice("已向全部在线设备请求最新心跳。")}>
            <ArrowClockwise size={17} />
            刷新心跳
          </button>
          <button className="button button-primary" type="button" onClick={() => setNotice("已生成今日设备健康巡检报告。")}>
            <Wrench size={17} />
            生成巡检报告
          </button>
        </div>
      </header>

      <section className="metric-grid device-metrics" aria-label="设备概况">
        <article className="metric-card metric-card--success">
          <span>在线设备</span><strong>{onlineCount}</strong><small>心跳正常</small>
        </article>
        <article className="metric-card metric-card--warning">
          <span>性能降级</span><strong>{degradedCount}</strong><small>需安排复核</small>
        </article>
        <article className="metric-card metric-card--critical">
          <span>离线设备</span><strong>{offlineCount}</strong><small>边端缓存兜底</small>
        </article>
        <article className="metric-card metric-card--info">
          <span>平均数据可信度</span><strong>85.5%</strong><small>最近10分钟</small>
        </article>
      </section>

      <div className="operation-notice" role="status" aria-live="polite">
        <Pulse size={18} weight="fill" />
        <span>{notice}</span>
      </div>

      <section className="filter-bar" aria-label="设备筛选">
        <div className="filter-bar-title"><Funnel size={17} />筛选</div>
        <label className="search-field">
          <MagnifyingGlass size={17} />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索设备编号或点位" />
        </label>
        <label className="field-inline">
          <span>状态</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {filterOptions.deviceStatuses.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label className="field-inline">
          <span>模式</span>
          <select value={mode} onChange={(event) => setMode(event.target.value)}>
            {filterOptions.deviceModes.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <span className="filter-result-count">显示 {filteredDevices.length} / {devices.length}</span>
      </section>

      <div className="devices-workspace">
        <section className="panel device-table-panel" aria-label="设备列表">
          <header className="panel-header">
            <div>
              <h2>设备清单</h2>
              <p>优先展示离线与数据质量异常</p>
            </div>
          </header>
          <div className="table-scroll">
            <table className="data-table device-table">
              <thead>
                <tr>
                  <th>设备 / 点位</th>
                  <th>状态</th>
                  <th>工作模式</th>
                  <th>通信</th>
                  <th>DEM基线</th>
                  <th>数据可信度</th>
                  <th aria-label="查看详情" />
                </tr>
              </thead>
              <tbody>
                {filteredDevices.map((device) => (
                  <tr className={activeDevice.id === device.id ? "is-selected" : ""} key={device.id}>
                    <td>
                      <button className="table-primary-button" type="button" onClick={() => setSelectedId(device.id)}>
                        <strong>{device.id}</strong>
                        <span>{device.siteName}</span>
                      </button>
                    </td>
                    <td><span className={`status-badge status-badge--${statusTone(device.status)}`}>{device.statusLabel}</span></td>
                    <td>{device.mode}</td>
                    <td><strong>{device.network}</strong><span className="table-subtext">{device.signal} dBm</span></td>
                    <td>
                      <span className={device.demAge > 30 ? "text-warning" : ""}>{device.demAge} 天</span>
                      {device.demAge > 30 && <Warning size={15} weight="fill" />}
                    </td>
                    <td>
                      <div className="inline-progress">
                        <span><i style={{ "--progress-value": `${device.dataConfidence}%` }} /></span>
                        <strong>{device.dataConfidence}%</strong>
                      </div>
                    </td>
                    <td><button className="icon-button" type="button" onClick={() => setSelectedId(device.id)} aria-label={`查看${device.id}详情`}>›</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filteredDevices.length === 0 && (
            <div className="empty-state"><HardDrives size={28} /><strong>无匹配设备</strong><span>请调整筛选条件。</span></div>
          )}
        </section>

        <aside className="panel device-detail-panel" aria-label="设备详情">
          <header className="device-detail-header">
            <div className={`device-status-icon device-status-icon--${statusTone(activeDevice.status)}`}>
              {activeDevice.status === "offline" ? <XCircle size={26} weight="fill" /> : <Cpu size={26} weight="fill" />}
            </div>
            <div>
              <div className="site-title-line">
                <h2>{activeDevice.id}</h2>
                <span className={`status-badge status-badge--${statusTone(activeDevice.status)}`}>{activeDevice.statusLabel}</span>
              </div>
              <p>{activeDevice.siteName} · {activeDevice.model}</p>
            </div>
          </header>

          <div className="device-mode-banner">
            <div>
              {activeDevice.mode === "降雨模式" ? <CloudRain size={22} weight="fill" /> : <Lightning size={22} weight="fill" />}
              <span>当前工作模式</span>
            </div>
            <strong>{activeDevice.mode}</strong>
          </div>

          <div className="device-health-grid">
            <article className="health-reading">
              <BatteryCharging size={20} />
              <span>供电</span>
              <strong>{activeDevice.power}</strong>
              <small>{activeDevice.powerValue}%</small>
            </article>
            <article className="health-reading">
              <WifiHigh size={20} />
              <span>通信</span>
              <strong>{activeDevice.network}</strong>
              <small>{activeDevice.signal} dBm</small>
            </article>
            <article className="health-reading">
              <Camera size={20} />
              <span>图像质量</span>
              <strong>{activeDevice.cameraQuality}%</strong>
              <small>{activeDevice.camera}</small>
            </article>
            <article className="health-reading">
              <Cpu size={20} />
              <span>设备温度</span>
              <strong>{activeDevice.temperature}℃</strong>
              <small>运行正常</small>
            </article>
          </div>

          <section className="device-section">
            <header><h3>传感器与数据</h3></header>
            <dl className="detail-list">
              <div><dt>激光雷达</dt><dd>{activeDevice.lidar}</dd></div>
              <div><dt>摄像头</dt><dd>{activeDevice.camera}</dd></div>
              <div><dt>最近心跳</dt><dd>{activeDevice.lastHeartbeat}</dd></div>
              <div><dt>最近DEM扫描</dt><dd>{activeDevice.lastScan}</dd></div>
              <div><dt>上行策略</dt><dd>{activeDevice.transport}</dd></div>
              <div><dt>固件版本</dt><dd>{activeDevice.firmware}</dd></div>
              <div><dt>下次维护</dt><dd className={activeDevice.nextMaintenance === "立即检查" ? "text-critical" : ""}>{activeDevice.nextMaintenance}</dd></div>
            </dl>
          </section>

          {activeDevice.demAge > 30 && (
            <div className="inline-alert inline-alert--warning">
              <Warning size={19} weight="fill" />
              <div><strong>DEM基线可能失准</strong><span>距上次扫描已超过30天，建议天气转晴后补扫。</span></div>
            </div>
          )}

          <div className="device-action-stack">
            <button className="button button-secondary" type="button" onClick={runSelfCheck}>
              <Pulse size={17} />远程自检
            </button>
            <button className="button button-secondary" type="button" onClick={switchMode}>
              <ArrowClockwise size={17} />切换工作模式
            </button>
            <button className="button button-primary" type="button" onClick={triggerScan}>
              <CheckCircle size={17} />安排DEM补扫
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default DevicesPage;
