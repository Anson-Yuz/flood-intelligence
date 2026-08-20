import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  ArrowsLeftRight,
  CalendarBlank,
  CaretRight,
  ChartLineDown,
  CheckCircle,
  Coins,
  DownloadSimple,
  Funnel,
  MagnifyingGlass,
  MapTrifold,
  SlidersHorizontal,
  Target,
  TrendDown,
  Warning,
  Wrench,
} from "@phosphor-icons/react";
import { filterOptions, maintenanceRoads } from "../data/demoData";

const levelOptions = [
  { value: "all", label: "全部优先级" },
  { value: "critical", label: "立即干预" },
  { value: "high", label: "近期计划" },
  { value: "medium", label: "持续观察" },
  { value: "normal", label: "状态稳定" },
];

const budgets = [20, 40, 60, 100];

export function MaintenancePage() {
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState("全部辖区");
  const [level, setLevel] = useState("all");
  const [weights, setWeights] = useState({ deterioration: 40, traffic: 25, flood: 35 });
  const [budget, setBudget] = useState(60);
  const [selectedId, setSelectedId] = useState(maintenanceRoads[0].id);
  const [plannedIds, setPlannedIds] = useState([maintenanceRoads[0].id]);
  const [comparison, setComparison] = useState("本月 vs 上月");
  const [notice, setNotice] = useState("优先级依据劣化速率、交通量与积水风险综合计算，支持人工调整权重。 ");

  const totalWeight = weights.deterioration + weights.traffic + weights.flood;

  const rankedRoads = useMemo(
    () =>
      maintenanceRoads
        .map((road) => ({
          ...road,
          score: Math.round(
            (road.deterioration * weights.deterioration + road.traffic * weights.traffic + road.flood * weights.flood) /
              totalWeight,
          ),
        }))
        .sort((a, b) => b.score - a.score)
        .map((road, index) => ({ ...road, dynamicRank: index + 1 })),
    [weights, totalWeight],
  );

  const filteredRoads = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return rankedRoads.filter((road) => {
      const matchesQuery = !normalized || road.name.toLowerCase().includes(normalized) || road.id.toLowerCase().includes(normalized);
      const matchesDistrict = district === "全部辖区" || road.district === district;
      const matchesLevel = level === "all" || road.level === level;
      return matchesQuery && matchesDistrict && matchesLevel;
    });
  }, [rankedRoads, query, district, level]);

  const recommendedRoads = useMemo(() => {
    let spent = 0;
    const selected = [];
    rankedRoads.forEach((road) => {
      if (spent + road.estimate <= budget) {
        selected.push(road);
        spent += road.estimate;
      }
    });
    return { roads: selected, spent };
  }, [rankedRoads, budget]);

  const activeRoad = rankedRoads.find((road) => road.id === selectedId) ?? filteredRoads[0] ?? rankedRoads[0];
  const inPlan = plannedIds.includes(activeRoad.id);

  const chartOption = useMemo(
    () => ({
      animationDuration: 450,
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(9, 23, 40, 0.96)",
        borderColor: "#2b4663",
        textStyle: { color: "#e8f1fa" },
        formatter: (params) => `测点 ${params[0].axisValue}<br/>高程变化 <b>${params[0].value} mm</b>`,
      },
      grid: { left: 52, right: 20, top: 38, bottom: 34 },
      xAxis: {
        type: "category",
        data: activeRoad.profile.map((_, index) => index + 1),
        axisLabel: { color: "#8ea1b5" },
        axisLine: { lineStyle: { color: "#36516b" } },
      },
      yAxis: {
        type: "value",
        name: "高程差 / mm",
        min: Math.min(-35, Math.min(...activeRoad.profile) - 4),
        max: 5,
        axisLabel: { color: "#8ea1b5" },
        nameTextStyle: { color: "#8ea1b5" },
        splitLine: { lineStyle: { color: "rgba(109, 137, 162, 0.16)" } },
      },
      series: [
        {
          type: "line",
          smooth: 0.35,
          symbolSize: 7,
          data: activeRoad.profile,
          lineStyle: { color: "#ffb84d", width: 3 },
          itemStyle: { color: "#ffb84d", borderColor: "#102538", borderWidth: 2 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(255, 184, 77, 0.03)" },
                { offset: 1, color: "rgba(255, 91, 103, 0.35)" },
              ],
            },
          },
          markLine: {
            symbol: "none",
            silent: true,
            lineStyle: { color: "#ff5b67", type: "dashed" },
            label: { color: "#ff7c86", formatter: "干预线 -20mm" },
            data: [{ yAxis: -20 }],
          },
        },
      ],
    }),
    [activeRoad],
  );

  const updateWeight = (key, value) => {
    setWeights((current) => ({ ...current, [key]: Number(value) }));
  };

  const togglePlan = () => {
    setPlannedIds((current) => (current.includes(activeRoad.id) ? current.filter((id) => id !== activeRoad.id) : [...current, activeRoad.id]));
    setNotice(inPlan ? `已将 ${activeRoad.name} 从养护草案移除。` : `已将 ${activeRoad.name} 纳入近期养护草案。`);
  };

  const generatePlan = () => {
    setPlannedIds(recommendedRoads.roads.map((road) => road.id));
    setNotice(`已按 ${budget} 万元预算生成建议：覆盖 ${recommendedRoads.roads.length} 段道路，预计投入 ${recommendedRoads.spent} 万元。`);
  };

  const exportPlan = () => {
    const payload = {
      label: "预鉴平台模拟养护建议",
      weights,
      budget,
      plannedRoads: rankedRoads.filter((road) => plannedIds.includes(road.id)),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "yujian-maintenance-plan.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice(`已导出包含 ${plannedIds.length} 段道路的模拟养护清单。`);
  };

  return (
    <div className="subpage maintenance-page" data-page="maintenance">
      <header className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow"><Wrench size={16} weight="fill" />路况养护 · 二期功能原型</div>
          <h1>道路养护优先级决策</h1>
          <p>用连续DEM变化回答“有限预算应该先修哪条路”。</p>
        </div>
        <div className="page-header-actions">
          <span className="demo-data-badge">二期预留 · 模拟排序 · 非真实算法结果</span>
          <button className="button button-secondary" type="button" onClick={exportPlan}>
            <DownloadSimple size={17} />导出清单
          </button>
          <button className="button button-primary" type="button" onClick={generatePlan}>
            <Target size={17} weight="fill" />生成预算建议
          </button>
        </div>
      </header>

      <section className="metric-grid maintenance-metrics" aria-label="道路状况概况">
        <article className="metric-card metric-card--critical"><span>需立即干预</span><strong>2<small>段</small></strong><small>最高沉降 31mm</small></article>
        <article className="metric-card metric-card--warning"><span>沉降加速路段</span><strong>3<small>段</small></strong><small>较上月 +1</small></article>
        <article className="metric-card metric-card--info"><span>连续监测覆盖</span><strong>18.6<small>km</small></strong><small>重点道路 73%</small></article>
        <article className="metric-card metric-card--success"><span>预防性养护机会</span><strong>5<small>项</small></strong><small>避免小问题拖大</small></article>
      </section>

      <div className="operation-notice" role="status" aria-live="polite">
        <Coins size={18} weight="fill" />
        <span>{notice}</span>
      </div>

      <section className="filter-bar" aria-label="路况筛选">
        <div className="filter-bar-title"><Funnel size={17} />筛选</div>
        <label className="search-field">
          <MagnifyingGlass size={17} />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索道路或监测段编号" />
        </label>
        <label className="field-inline">
          <span>辖区</span>
          <select value={district} onChange={(event) => setDistrict(event.target.value)}>
            {filterOptions.districts.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label className="field-inline">
          <span>优先级</span>
          <select value={level} onChange={(event) => setLevel(event.target.value)}>
            {levelOptions.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
        </label>
        <span className="filter-result-count">共 {filteredRoads.length} 段</span>
      </section>

      <div className="maintenance-workspace">
        <section
          className={`panel maintenance-ranking-panel ${filteredRoads.length > 0 ? "has-results" : "is-empty"}`}
          aria-label="道路优先级排名"
        >
          <header className="panel-header">
            <div><h2>养护优先级排名</h2><p>点击道路查看DEM变化与建议</p></div>
            <span className="count-badge">Top {filteredRoads.length}</span>
          </header>
          <div className="table-scroll">
            <table className="data-table maintenance-table">
              <thead>
                <tr>
                  <th>排名</th><th>道路监测段</th><th>综合分</th><th>沉降</th><th>IRI估算</th><th>建议</th><th />
                </tr>
              </thead>
              <tbody>
                {filteredRoads.map((road) => (
                  <tr className={activeRoad.id === road.id ? "is-selected" : ""} key={road.id}>
                    <td><span className={`rank-number ${road.dynamicRank <= 3 ? "rank-number--top" : ""}`}>{road.dynamicRank}</span></td>
                    <td>
                      <button className="table-primary-button" type="button" onClick={() => setSelectedId(road.id)}>
                        <strong>{road.name}</strong><span>{road.district} · {road.id}</span>
                      </button>
                    </td>
                    <td><strong className={`score-value score-value--${road.level}`}>{road.score}</strong></td>
                    <td><strong>{road.maxSettlement} mm</strong><span className="table-subtext">{road.settlementRate} mm/月</span></td>
                    <td>{road.iri}</td>
                    <td><span className={`status-badge status-badge--${road.level}`}>{road.levelLabel}</span></td>
                    <td><button className="icon-button" type="button" onClick={() => setSelectedId(road.id)} aria-label={`查看${road.name}`}><CaretRight size={16} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filteredRoads.length === 0 && (
            <div className="empty-state"><MapTrifold size={28} /><strong>没有匹配路段</strong><span>请调整筛选条件。</span></div>
          )}
        </section>

        <aside className="panel maintenance-model-panel" aria-label="优先级权重与预算">
          <header className="panel-header">
            <div><h2>决策模型</h2><p>权重变化会实时重排道路</p></div>
            <SlidersHorizontal size={20} />
          </header>
          <div className="weight-controls">
            <label className="range-field range-field--compact">
              <span>路面劣化速率<strong>{weights.deterioration}</strong></span>
              <input type="range" min="5" max="80" value={weights.deterioration} onChange={(event) => updateWeight("deterioration", event.target.value)} />
            </label>
            <label className="range-field range-field--compact">
              <span>交通量权重<strong>{weights.traffic}</strong></span>
              <input type="range" min="5" max="80" value={weights.traffic} onChange={(event) => updateWeight("traffic", event.target.value)} />
            </label>
            <label className="range-field range-field--compact">
              <span>积水风险权重<strong>{weights.flood}</strong></span>
              <input type="range" min="5" max="80" value={weights.flood} onChange={(event) => updateWeight("flood", event.target.value)} />
            </label>
          </div>
          <div className="model-formula">
            <span>综合分</span>
            <code>劣化速率 × {Math.round((weights.deterioration / totalWeight) * 100)}%</code>
            <code>交通量 × {Math.round((weights.traffic / totalWeight) * 100)}%</code>
            <code>积水风险 × {Math.round((weights.flood / totalWeight) * 100)}%</code>
          </div>

          <section className="budget-simulator">
            <div className="section-title-row"><h3>预算模拟</h3><span>单位：万元</span></div>
            <div className="budget-options">
              {budgets.map((value) => (
                <button type="button" key={value} className={budget === value ? "is-active" : ""} onClick={() => setBudget(value)}>{value}</button>
              ))}
            </div>
            <div className="budget-result">
              <div><span>建议覆盖</span><strong>{recommendedRoads.roads.length}<small>段</small></strong></div>
              <div><span>预计投入</span><strong>{recommendedRoads.spent}<small>万</small></strong></div>
              <div><span>剩余预算</span><strong>{budget - recommendedRoads.spent}<small>万</small></strong></div>
            </div>
            <ol className="budget-road-list">
              {recommendedRoads.roads.map((road, index) => (
                <li key={road.id}><span>{index + 1}</span><strong>{road.name.split(" K")[0]}</strong><em>{road.estimate}万</em></li>
              ))}
            </ol>
            <button className="button button-primary button-block" type="button" onClick={generatePlan}>
              <Target size={17} />生成养护草案
            </button>
          </section>
        </aside>

        <section className="panel road-detail-panel" aria-label="路段详情">
          <header className="road-detail-header">
            <div>
              <div className="site-title-line">
                <span className={`status-badge status-badge--${activeRoad.level}`}>{activeRoad.levelLabel}</span>
                <h2>{activeRoad.name}</h2>
              </div>
              <p>{activeRoad.district} · 最近扫描 {activeRoad.lastScan} · {activeRoad.trend}</p>
            </div>
            <div className="road-detail-actions">
              <div className="segmented-control segmented-control--compact">
                {["本月 vs 上月", "本月 vs 年初"].map((item) => (
                  <button type="button" key={item} className={comparison === item ? "is-active" : ""} onClick={() => setComparison(item)}>{item}</button>
                ))}
              </div>
              <button className={`button ${inPlan ? "button-secondary" : "button-primary"}`} type="button" onClick={togglePlan}>
                {inPlan ? <CheckCircle size={17} weight="fill" /> : <Wrench size={17} />}
                {inPlan ? "已纳入草案" : "纳入养护草案"}
              </button>
            </div>
          </header>

          <div className="road-detail-grid">
            <section className="dem-comparison-card">
              <div className="section-title-row">
                <div><h3>DEM 高程差分</h3><p>{comparison} · 0.10m栅格</p></div>
                <ArrowsLeftRight size={19} />
              </div>
              <div className="dem-grid" aria-label="道路高程差分热力图">
                {activeRoad.profile.flatMap((value, rowIndex) =>
                  [0, 1, 2, 3].map((columnIndex) => {
                    const delta = Math.round(value * (0.74 + columnIndex * 0.08) + ((rowIndex + columnIndex) % 3));
                    return (
                      <span
                        key={`${rowIndex}-${columnIndex}`}
                        className={`dem-cell ${delta <= -20 ? "dem-cell--critical" : delta <= -10 ? "dem-cell--warning" : "dem-cell--normal"}`}
                        title={`高程变化 ${delta} mm`}
                      />
                    );
                  }),
                )}
              </div>
              <div className="dem-legend"><span>0 mm</span><i /><i /><i /><span>≤ -30 mm</span></div>
            </section>

            <section className="settlement-chart-card">
              <div className="section-title-row">
                <div><h3>纵向沉降剖面</h3><p>最大沉降 {activeRoad.maxSettlement} mm · 变化速率 {activeRoad.settlementRate} mm/月</p></div>
                <ChartLineDown size={20} />
              </div>
              <ReactECharts className="settlement-chart" option={chartOption} style={{ height: 250, width: "100%" }} />
            </section>

            <aside className="road-assessment-card">
              <h3>路段评估</h3>
              <div className="assessment-score"><span>综合优先级</span><strong>{activeRoad.score}</strong><small>/ 100</small></div>
              <dl className="compact-definition-grid">
                <div><dt>IRI 近似值</dt><dd>{activeRoad.iri}</dd></div>
                <div><dt>最大沉降</dt><dd>{activeRoad.maxSettlement} mm</dd></div>
                <div><dt>月变化率</dt><dd>{activeRoad.settlementRate} mm</dd></div>
                <div><dt>预估投入</dt><dd>{activeRoad.estimate} 万</dd></div>
              </dl>
              <div className="road-recommendation">
                {activeRoad.level === "critical" ? <Warning size={20} weight="fill" /> : <TrendDown size={20} />}
                <div><span>系统建议</span><p>{activeRoad.recommendation}</p></div>
              </div>
              <div className="road-followup">
                <CalendarBlank size={18} />
                <span>建议复扫周期</span>
                <strong>{activeRoad.level === "critical" ? "施工后立即" : activeRoad.level === "high" ? "1个月" : "3个月"}</strong>
              </div>
            </aside>
          </div>
        </section>
      </div>
    </div>
  );
}

export default MaintenancePage;
