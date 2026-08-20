import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import {
  ArrowClockwise,
  ArrowSquareOut,
  BellRinging,
  CaretRight,
  CheckCircle,
  ClockCountdown,
  CloudRain,
  Funnel,
  MapTrifold,
  TrendUp,
  Warning,
} from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
import { ShenzhenRiskMap } from "../components/ShenzhenRiskMap";
import { useAlertVisual } from "../context/AlertVisualContext";
import {
  demoMeta,
  overviewMetrics,
  riskLevels,
  siteData,
} from "../data/demoData";

const horizonOptions = [
  { value: 0, label: "当前" },
  { value: 15, label: "15分钟" },
  { value: 30, label: "30分钟" },
  { value: 60, label: "60分钟" },
];

const districtOptions = [
  "全部辖区",
  ...Array.from(new Set(siteData.map((site) => site.district))),
];

function getDepthAtHorizon(site, horizon) {
  if (horizon === 15) return site.forecast15;
  if (horizon === 30) return site.forecast30;
  if (horizon === 60) return site.forecast60;
  return site.currentDepth;
}

export function OverviewPage() {
  const navigate = useNavigate();
  const { setLevel } = useAlertVisual();
  const [district, setDistrict] = useState("全部辖区");
  const [risk, setRisk] = useState("all");
  const [horizon, setHorizon] = useState(15);
  const [selectedId, setSelectedId] = useState(siteData[0].id);
  const [focusRequest, setFocusRequest] = useState({ siteId: null, sequence: 0 });
  const [layer, setLayer] = useState("积水风险");
  const [syncNote, setSyncNote] = useState(`更新于 ${demoMeta.updatedAt.slice(11)}`);

  const filteredSites = useMemo(
    () =>
      siteData.filter((site) => {
        const inDistrict = district === "全部辖区" || site.district === district;
        const inRisk = risk === "all" || site.risk === risk;
        return inDistrict && inRisk;
      }),
    [district, risk],
  );

  const selectedSite =
    filteredSites.find((site) => site.id === selectedId) ?? filteredSites[0] ?? null;

  const riskQueue = useMemo(
    () =>
      filteredSites
        .filter((site) => site.risk !== "normal")
        .slice()
        .sort((a, b) => (a.eta ?? 999) - (b.eta ?? 999)),
    [filteredSites],
  );

  const focusSite = useCallback((siteId) => {
    setSelectedId(siteId);
    setFocusRequest((current) => ({
      siteId,
      sequence: current.sequence + 1,
    }));
  }, []);

  useEffect(() => {
    if (filteredSites.length === 0) {
      if (selectedId !== null) setSelectedId(null);
      return;
    }
    if (!filteredSites.some((site) => site.id === selectedId)) {
      setSelectedId(filteredSites[0].id);
    }
  }, [filteredSites, selectedId]);

  const handleDistrictChange = (event) => {
    const nextDistrict = event.target.value;
    setDistrict(nextDistrict);
    setRisk("all");

    if (nextDistrict === "全部辖区") {
      setSelectedId(siteData[0].id);
      setFocusRequest((current) => ({
        siteId: null,
        sequence: current.sequence + 1,
      }));
      return;
    }

    const districtSite = siteData.find((site) => site.district === nextDistrict);
    if (districtSite) focusSite(districtSite.id);
  };

  const handleRiskChange = (event) => {
    const nextRisk = event.target.value;
    setRisk(nextRisk);

    const nextSites = siteData.filter((site) => {
      const inDistrict = district === "全部辖区" || site.district === district;
      return inDistrict && (nextRisk === "all" || site.risk === nextRisk);
    });

    if (nextSites.length === 0) {
      setSelectedId(null);
      setFocusRequest((current) => ({
        siteId: null,
        sequence: current.sequence + 1,
      }));
    } else if (!nextSites.some((site) => site.id === selectedId)) {
      focusSite(nextSites[0].id);
    }
  };

  useLayoutEffect(() => {
    const alertLevel =
      !selectedSite
        ? "none"
        : selectedSite.risk === "critical"
          ? "critical"
          : selectedSite.risk === "medium"
            ? "medium"
            : "none";
    setLevel(alertLevel);
  }, [selectedSite?.risk, setLevel]);

  useEffect(() => () => setLevel("none"), [setLevel]);

  const handleRefresh = () => {
    const now = new Date();
    const time = now.toLocaleTimeString("zh-CN", { hour12: false });
    setSyncNote(`模拟刷新 ${time}`);
  };

  const handleResetFilters = () => {
    setDistrict("全部辖区");
    setRisk("all");
    focusSite(siteData[0].id);
  };

  return (
    <div className="subpage overview-page" data-page="overview">
      <header className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow">
            <MapTrifold size={16} weight="fill" />
            {demoMeta.city}全域态势
          </div>
          <h1>深圳市城市积水风险总览</h1>
          <p>统一查看十区点位模拟风险、短临预报与处置进度，实测链路接入后自动替换。</p>
        </div>
        <div className="page-header-actions">
          <span className="demo-data-badge">{demoMeta.label}</span>
          <span className="sync-note" aria-live="polite">{syncNote}</span>
          <button className="button button-secondary" type="button" onClick={handleRefresh}>
            <ArrowClockwise size={17} />
            刷新数据
          </button>
          <button className="button button-primary" type="button" onClick={() => navigate("/events")}>
            <BellRinging size={17} weight="fill" />
            进入预警中心
          </button>
        </div>
      </header>

      <section className="metric-grid overview-metrics" aria-label="核心指标">
        {overviewMetrics.map((metric) => (
          <article className={`metric-card metric-card--${metric.tone}`} key={metric.id}>
            <div className="metric-card-label">{metric.label}</div>
            <div className="metric-card-row">
              <strong>{metric.value}</strong>
              <span>{metric.change}</span>
            </div>
          </article>
        ))}
      </section>

      <section className="filter-bar" aria-label="总览筛选">
        <div className="filter-bar-title">
          <Funnel size={17} />
          筛选
        </div>
        <label className="field-inline">
          <span>辖区</span>
          <select value={district} onChange={handleDistrictChange}>
            {districtOptions.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          <span>风险</span>
          <select value={risk} onChange={handleRiskChange}>
            {riskLevels.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <div className="segmented-control segmented-control--compact" aria-label="预测时刻">
          {horizonOptions.map((option) => (
            <button
              className={horizon === option.value ? "is-active" : ""}
              type="button"
              key={option.value}
              onClick={() => setHorizon(option.value)}
              aria-pressed={horizon === option.value}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="weather-strip">
          <CloudRain size={18} weight="fill" />
          <span>{demoMeta.weather}</span>
        </div>
      </section>

      <div className="overview-workspace">
        <section className="panel map-panel" aria-label="风险点位地图">
          <header className="panel-header">
            <div>
              <h2>深圳辖区风险态势</h2>
              <p>
                {horizon === 0
                  ? "显示当前模拟水深"
                  : `显示未来${horizon}分钟模拟预测水深`}
              </p>
            </div>
            <div className="layer-switcher" aria-label="地图图层">
              {["积水风险", "设备状态", "路面沉降"].map((item) => (
                <button
                  type="button"
                  key={item}
                  className={layer === item ? "is-active" : ""}
                  onClick={() => setLayer(item)}
                  aria-pressed={layer === item}
                >
                  {item}
                </button>
              ))}
            </div>
          </header>

          <ShenzhenRiskMap
            sites={filteredSites}
            selectedSite={selectedSite}
            horizon={horizon}
            layer={layer}
            focusRequest={focusRequest}
            onSelect={focusSite}
          />
        </section>

        <aside className="panel risk-queue-panel" aria-label="风险队列">
          <header className="panel-header">
            <div>
              <h2>优先处置队列</h2>
              <p>按模拟达险时间排序</p>
            </div>
            <span className="count-badge">{riskQueue.length}</span>
          </header>
          <div className="risk-queue-list">
            {riskQueue.map((site) => (
              <button
                className={`risk-queue-item ${selectedSite.id === site.id ? "is-selected" : ""}`}
                type="button"
                key={site.id}
                onClick={() => focusSite(site.id)}
              >
                <span className={`status-dot status-dot--${site.risk}`} />
                <span className="risk-queue-content">
                  <strong>{site.name}</strong>
                  <span>{site.district} · 当前模拟 {site.currentDepth} cm</span>
                </span>
                <span className="risk-queue-eta">
                  <ClockCountdown size={15} />
                  {site.eta ? `${site.eta} 分钟` : "未达险"}
                </span>
                <CaretRight size={16} />
              </button>
            ))}
            {riskQueue.length === 0 && (
              <div className="empty-state empty-state--queue">
                <CheckCircle size={25} />
                <strong>当前筛选下无待处置点位</strong>
                <span>可切换辖区或风险等级继续查看。</span>
              </div>
            )}
          </div>
        </aside>

        <section className="panel site-inspector-panel" aria-label="选中点位详情">
          {selectedSite ? (
            <>
          <header className="site-inspector-header">
            <div>
              <div className="site-title-line">
                <span className={`status-badge status-badge--${selectedSite.risk}`}>
                  {selectedSite.riskLabel}
                </span>
                <h2>{selectedSite.name}</h2>
              </div>
              <p>{selectedSite.district} · {selectedSite.type} · {selectedSite.deviceId}</p>
            </div>
            <button
              className="button button-ghost"
              type="button"
              onClick={() => navigate("/events", { state: { siteId: selectedSite.id } })}
            >
              查看事件详情
              <CaretRight size={16} />
            </button>
          </header>

          <div className="site-inspector-grid">
            <figure className="site-live-visual">
              <img src={selectedSite.sceneImage} alt={selectedSite.sceneAlt} />
              <figcaption className="scene-context-label">
                辖区实景 · 非实时监控
              </figcaption>
              <a
                className="scene-credit-link"
                href={selectedSite.sceneSource}
                target="_blank"
                rel="noreferrer"
                title={selectedSite.sceneCredit}
              >
                <span>{selectedSite.sceneCredit}</span>
                <ArrowSquareOut size={13} />
              </a>
            </figure>

            <div className="site-vitals">
              <div className="primary-reading">
                <span>当前模拟最大水深</span>
                <strong>{selectedSite.maxDepth}<small>cm</small></strong>
                <em className={`trend-chip trend-chip--${selectedSite.riseRate > 0.6 ? "up" : "stable"}`}>
                  <TrendUp size={14} /> {selectedSite.riseRate} cm/min
                </em>
              </div>
              <dl className="compact-definition-grid">
                <div><dt>模拟积水面积</dt><dd>{selectedSite.area} ㎡</dd></div>
                <div><dt>模拟估算体积</dt><dd>{selectedSite.volume} m³</dd></div>
                <div><dt>排水状态</dt><dd>{selectedSite.saturation}</dd></div>
                <div><dt>数据更新</dt><dd>{selectedSite.updatedAt}</dd></div>
              </dl>
            </div>

            <div className="forecast-summary">
              <div className="forecast-summary-head">
                <span>短临模拟预报</span>
                <strong>{selectedSite.confidence}% 置信度</strong>
              </div>
              <div className="forecast-bars">
                {[15, 30, 60].map((minute) => {
                  const depth = getDepthAtHorizon(selectedSite, minute);
                  return (
                    <div className="forecast-bar-row" key={minute}>
                      <span>{minute}分钟</span>
                      <div className="forecast-bar-track">
                        <i style={{ "--bar-value": `${Math.min(depth / 60, 1) * 100}%` }} />
                      </div>
                      <strong>{depth} cm</strong>
                    </div>
                  );
                })}
              </div>
              <div className="forecast-alert-line">
                {selectedSite.eta
                  ? <Warning size={18} weight="fill" />
                  : <CheckCircle size={18} weight="fill" />}
                <span>
                  {selectedSite.eta
                    ? `模拟预计 ${selectedSite.eta} 分钟后达到风险阈值`
                    : "模拟未来60分钟预计不触及风险阈值"}
                </span>
              </div>
            </div>

            <div className="recommendation-card">
              <span className="recommendation-label">系统模拟处置建议</span>
              <p>{selectedSite.recommendation}</p>
              <div className="recommendation-meta">
                <span>规则引擎待接入</span>
                <span>实测链路待接入</span>
              </div>
            </div>
          </div>
            </>
          ) : (
            <div className="empty-state site-inspector-empty" role="status">
              <MapTrifold size={30} />
              <strong>当前筛选下暂无点位详情</strong>
              <span>地图、处置队列与告警提示已同步清空。</span>
              <button className="button button-secondary" type="button" onClick={handleResetFilters}>
                清除筛选
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default OverviewPage;
