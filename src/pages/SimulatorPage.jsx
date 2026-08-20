import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  ArrowCounterClockwise,
  Flask,
  CheckCircle,
  CloudRain,
  Gauge,
  Lightning,
  Play,
  SlidersHorizontal,
  Sparkle,
  Timer,
  Warning,
} from "@phosphor-icons/react";
import { simulatorPresets } from "../data/demoData";

function rainfallFactor(value) {
  if (value >= 30) return 1.8;
  if (value >= 15) return 1.3;
  if (value > 0) return 1;
  return 0.7;
}

function getRisk(depth) {
  if (depth >= 35) return { tone: "critical", label: "建议立即管控" };
  if (depth >= 25) return { tone: "high", label: "进入高风险区间" };
  if (depth >= 15) return { tone: "medium", label: "需要持续关注" };
  return { tone: "normal", label: "风险可控" };
}

export function SimulatorPage() {
  const [presetId, setPresetId] = useState(simulatorPresets[0].id);
  const preset = simulatorPresets.find((item) => item.id === presetId) ?? simulatorPresets[0];
  const [rainfall, setRainfall] = useState(preset.rainfall);
  const [currentDepth, setCurrentDepth] = useState(preset.currentDepth);
  const [baseSlope, setBaseSlope] = useState(preset.baseSlope);
  const [drainage, setDrainage] = useState(preset.drainage);
  const [area, setArea] = useState(preset.area);
  const [anomaly, setAnomaly] = useState(false);
  const [runCount, setRunCount] = useState(1);
  const [notice, setNotice] = useState("已载入下穿隧道强降雨演示场景。调整参数后点击开始推演。 ");

  const selectPreset = (nextPreset) => {
    setPresetId(nextPreset.id);
    setRainfall(nextPreset.rainfall);
    setCurrentDepth(nextPreset.currentDepth);
    setBaseSlope(nextPreset.baseSlope);
    setDrainage(nextPreset.drainage);
    setArea(nextPreset.area);
    setAnomaly(false);
    setNotice(`已载入“${nextPreset.name}”，参数已恢复为场景预设。`);
  };

  const results = useMemo(() => {
    const rainCorrection = rainfallFactor(rainfall);
    const drainageCorrection = Math.max(0.45, 1.2 - drainage / 250);
    const netSlope = baseSlope * rainCorrection * drainageCorrection;
    const points = [];
    for (let minute = 0; minute <= 60; minute += 5) {
      const firstStage = Math.min(minute, 15) * netSlope;
      const secondStage = Math.max(0, minute - 15) * netSlope * 0.58;
      const depth = Math.min(preset.maxDepth, currentDepth + firstStage + secondStage);
      points.push({ minute, depth: Number(depth.toFixed(1)) });
    }
    const depthAt = (minute) => points.find((point) => point.minute === minute)?.depth ?? currentDepth;
    const confidencePenalty = Math.abs(rainfall - preset.rainfall) * 0.22 + (anomaly ? 23 : 0);
    const confidence = Math.round(Math.max(52, Math.min(96, preset.confidence - confidencePenalty)));
    const findEta = (threshold) => {
      const match = points.find((point) => point.depth >= threshold);
      return match?.minute ?? null;
    };
    const volume = Number((area * depthAt(30) / 100 * 0.55).toFixed(1));
    return {
      rainCorrection,
      drainageCorrection,
      netSlope: Number(netSlope.toFixed(2)),
      points,
      forecast15: depthAt(15),
      forecast30: depthAt(30),
      forecast60: depthAt(60),
      eta30: findEta(30),
      eta35: findEta(35),
      confidence,
      volume,
      risk: getRisk(depthAt(15)),
    };
  }, [rainfall, currentDepth, baseSlope, drainage, area, anomaly, preset]);

  const chartOption = useMemo(
    () => ({
      animationDuration: 500,
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(9, 23, 40, 0.96)",
        borderColor: "#2b4663",
        textStyle: { color: "#e8f1fa" },
        formatter: (params) => `${params[0].axisValue} 分钟<br/>预测水深 <b>${params[0].value} cm</b>`,
      },
      grid: { left: 48, right: 22, top: 36, bottom: 38 },
      xAxis: {
        type: "category",
        name: "分钟",
        boundaryGap: false,
        data: results.points.map((point) => point.minute),
        axisLine: { lineStyle: { color: "#36516b" } },
        axisLabel: { color: "#8ea1b5" },
        nameTextStyle: { color: "#8ea1b5" },
      },
      yAxis: {
        type: "value",
        name: "水深 / cm",
        min: 0,
        max: 60,
        axisLabel: { color: "#8ea1b5" },
        nameTextStyle: { color: "#8ea1b5" },
        splitLine: { lineStyle: { color: "rgba(109, 137, 162, 0.16)" } },
      },
      series: [
        {
          type: "line",
          smooth: 0.28,
          data: results.points.map((point) => point.depth),
          symbolSize: 7,
          lineStyle: { color: "#19d3ff", width: 3 },
          itemStyle: { color: "#19d3ff", borderColor: "#07233a", borderWidth: 2 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(25, 211, 255, 0.34)" },
                { offset: 1, color: "rgba(25, 211, 255, 0.02)" },
              ],
            },
          },
          markLine: {
            silent: true,
            symbol: "none",
            label: { color: "#f7c86a", formatter: "风险阈值 30cm" },
            lineStyle: { color: "#f7b955", type: "dashed" },
            data: [{ yAxis: 30 }, { yAxis: 50, label: { formatter: "严重阈值 50cm", color: "#ff737e" }, lineStyle: { color: "#ff5a67" } }],
          },
        },
      ],
    }),
    [results],
  );

  const runSimulation = () => {
    setRunCount((count) => count + 1);
    setNotice(
      anomaly
        ? `第 ${runCount + 1} 次推演完成：异常帧已被L1剔除，置信度降至${results.confidence}%，仅内部记录。`
        : `第 ${runCount + 1} 次推演完成：预计${results.eta35 ?? "60分钟后仍未"}分钟达到35cm，置信度${results.confidence}%。`,
    );
  };

  return (
    <div className="subpage simulator-page" data-page="simulator">
      <header className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow"><Flask size={16} weight="fill" />推演沙盘</div>
          <h1>积水预报交互模拟器</h1>
          <p>用可解释参数演示“实测斜率—气象修正—案例修正—物理校验”的推演过程。</p>
        </div>
        <div className="page-header-actions">
          <span className="demo-data-badge">设计目标演示 · 非实测结论</span>
          <button className="button button-secondary" type="button" onClick={() => selectPreset(preset)}>
            <ArrowCounterClockwise size={17} />恢复预设
          </button>
          <button className="button button-primary" type="button" onClick={runSimulation}>
            <Play size={17} weight="fill" />开始推演
          </button>
        </div>
      </header>

      <div className="operation-notice" role="status" aria-live="polite">
        <Sparkle size={18} weight="fill" />
        <span>{notice}</span>
      </div>

      <div className="simulator-workspace">
        <aside className="panel simulator-controls-panel" aria-label="推演参数">
          <header className="panel-header">
            <div><h2>场景与参数</h2><p>可实时调整输入变量</p></div>
            <SlidersHorizontal size={20} />
          </header>

          <section className="preset-section">
            <h3>场景预设</h3>
            <div className="preset-list">
              {simulatorPresets.map((item) => (
                <button
                  type="button"
                  className={`preset-card ${presetId === item.id ? "is-selected" : ""}`}
                  onClick={() => selectPreset(item)}
                  key={item.id}
                >
                  <span className="preset-radio" />
                  <strong>{item.name}</strong>
                  <p>{item.description}</p>
                  <span className="preset-tags">{item.tags.map((tag) => <em key={tag}>{tag}</em>)}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="parameter-section">
            <h3>输入参数</h3>
            <label className="range-field">
              <span><CloudRain size={17} />未来30分钟降雨强度<strong>{rainfall} mm/h</strong></span>
              <input type="range" min="0" max="60" step="1" value={rainfall} onChange={(event) => setRainfall(Number(event.target.value))} />
              <small><span>无雨</span><span>暴雨</span></small>
            </label>
            <label className="range-field">
              <span><Gauge size={17} />当前最大水深<strong>{currentDepth} cm</strong></span>
              <input type="range" min="0" max="45" step="1" value={currentDepth} onChange={(event) => setCurrentDepth(Number(event.target.value))} />
              <small><span>0 cm</span><span>45 cm</span></small>
            </label>
            <label className="range-field">
              <span><Lightning size={17} />实测上涨斜率<strong>{baseSlope.toFixed(2)} cm/min</strong></span>
              <input type="range" min="0.05" max="2" step="0.05" value={baseSlope} onChange={(event) => setBaseSlope(Number(event.target.value))} />
              <small><span>缓慢</span><span>快速</span></small>
            </label>
            <label className="range-field">
              <span><Timer size={17} />排水能力评分<strong>{drainage}%</strong></span>
              <input type="range" min="20" max="100" step="1" value={drainage} onChange={(event) => setDrainage(Number(event.target.value))} />
              <small><span>接近饱和</span><span>排水充足</span></small>
            </label>
            <label className="number-field">
              <span>积水影响面积</span>
              <div><input type="number" min="20" max="750" value={area} onChange={(event) => setArea(Number(event.target.value))} /><em>㎡</em></div>
            </label>
            <label className="toggle-field toggle-field--danger">
              <span><strong>注入低质量图像帧</strong><small>演示L1异常剔除与置信度降级</small></span>
              <input type="checkbox" checked={anomaly} onChange={(event) => setAnomaly(event.target.checked)} />
              <i aria-hidden="true" />
            </label>
          </section>
        </aside>

        <main className="simulator-results">
          <section className="simulator-result-grid" aria-label="推演结果">
            <article className={`result-hero-card result-hero-card--${results.risk.tone}`}>
              <span>决策输出</span>
              <strong>{results.risk.label}</strong>
              <small>{results.confidence >= 85 ? "满足高置信自动联动门槛" : results.confidence >= 60 ? "需管理人员人工确认" : "仅内部记录，不外发"}</small>
            </article>
            <article className="result-metric"><span>15分钟预测</span><strong>{results.forecast15}<small>cm</small></strong></article>
            <article className="result-metric"><span>30分钟预测</span><strong>{results.forecast30}<small>cm</small></strong></article>
            <article className="result-metric"><span>预计达35cm</span><strong>{results.eta35 ?? "—"}<small>{results.eta35 ? "分钟" : ""}</small></strong></article>
            <article className="result-metric"><span>预报置信度</span><strong>{results.confidence}<small>%</small></strong></article>
          </section>

          <section className="panel simulator-chart-panel">
            <header className="panel-header">
              <div><h2>15 / 30 / 60 分钟积水趋势</h2><p>斜率修正后净上涨 {results.netSlope} cm/min · 30分钟估算体积 {results.volume} m³</p></div>
              <div className="chart-legend"><span><i className="legend-line legend-line--forecast" />预测曲线</span><span><i className="legend-line legend-line--threshold" />风险阈值</span></div>
            </header>
            <ReactECharts className="forecast-chart" option={chartOption} style={{ height: 340, width: "100%" }} />
          </section>

          <section className="panel reasoning-pipeline-panel">
            <header className="panel-header">
              <div><h2>四层推理流水线</h2><p>每一步输出均可反向审计</p></div>
              <span className="status-badge status-badge--success">物理约束通过</span>
            </header>
            <div className="reasoning-pipeline">
              <article className={`pipeline-step ${anomaly ? "pipeline-step--warning" : "pipeline-step--success"}`}>
                <span className="pipeline-index">L1</span>
                <div><strong>数据清洗</strong><p>{anomaly ? "异常图像帧已剔除，以缓存帧补位" : "有效像素率82%，数据可信"}</p></div>
                {anomaly ? <Warning size={19} weight="fill" /> : <CheckCircle size={19} weight="fill" />}
              </article>
              <article className="pipeline-step pipeline-step--success">
                <span className="pipeline-index">L2</span>
                <div><strong>状态分析</strong><p>当前{currentDepth}cm · 上涨{baseSlope.toFixed(2)}cm/min</p></div>
                <CheckCircle size={19} weight="fill" />
              </article>
              <article className="pipeline-step pipeline-step--success">
                <span className="pipeline-index">L3</span>
                <div><strong>趋势预判</strong><p>气象修正 ×{results.rainCorrection} · 净斜率{results.netSlope}</p></div>
                <CheckCircle size={19} weight="fill" />
              </article>
              <article className={`pipeline-step pipeline-step--${results.confidence >= 85 ? "critical" : "warning"}`}>
                <span className="pipeline-index">L4</span>
                <div><strong>决策输出</strong><p>{results.risk.label} · 置信度{results.confidence}%</p></div>
                {results.confidence >= 85 ? <Lightning size={19} weight="fill" /> : <Warning size={19} weight="fill" />}
              </article>
            </div>
            <div className="constraint-strip">
              <span><CheckCircle size={16} weight="fill" />水量守恒</span>
              <span><CheckCircle size={16} weight="fill" />持续降雨单调性</span>
              <span><CheckCircle size={16} weight="fill" />洼地深度上限 {preset.maxDepth}cm</span>
              <span>推演编号 SIM-{String(runCount).padStart(4, "0")}</span>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default SimulatorPage;
