import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowCounterClockwise,
  Broadcast,
  Camera,
  CaretRight,
  CheckCircle,
  Clock,
  CloudRain,
  Database,
  Eye,
  FileText,
  Info,
  LockKey,
  MapPin,
  PaperPlaneTilt,
  ShieldCheck,
  TrendUp,
  UserCircle,
  Warning,
  X,
} from "@phosphor-icons/react";
import { getRawEvidence, publishWarning, sendForManualReview } from "../api/client";
import { siteData } from "../data/demoData";
import { assetPath } from "../config/runtime";

const reviewSite = siteData[0];
const eventId = "YJ-20260710-0148";

const evidenceSteps = [
  {
    id: "L1",
    title: "数据可信",
    time: "14:19:51",
    tone: "success",
    summary: "有效像素率82%，DEM基线9天",
    detail: "异常帧已剔除，当前帧综合可信度94%",
  },
  {
    id: "L2",
    title: "状态确认",
    time: "14:19:58",
    tone: "info",
    summary: "最大水深22cm，面积286㎡",
    detail: "近5分钟上涨1.1cm/min，排水趋于饱和",
  },
  {
    id: "L3",
    title: "趋势预判",
    time: "14:20:06",
    tone: "warning",
    summary: "预计12分钟达到35cm",
    detail: "气象修正×1.8，相似案例 CASE-047 / 112",
  },
  {
    id: "L4",
    title: "物理校验",
    time: "14:20:08",
    tone: "critical",
    summary: "关闭道闸并发布绕行信息",
    detail: "置信度88%，满足高置信联动门槛",
  },
];

export function ReviewPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("待研判");
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState(null);
  const [busy, setBusy] = useState(false);
  const [rawEvidence, setRawEvidence] = useState(null);
  const [reviewReason, setReviewReason] = useState("需要现场人员复核积水边界与道闸状态");
  const [channels, setChannels] = useState({ gate: true, led: true, app: true, patrol: true });

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(null), 3600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const showToast = (message, tone = "success") => setToast({ message, tone });

  const openRawEvidence = async () => {
    setModal("raw");
    if (rawEvidence) return;
    setBusy(true);
    const result = await getRawEvidence(eventId);
    setRawEvidence(result);
    setBusy(false);
  };

  const handleManualReview = async () => {
    setBusy(true);
    const result = await sendForManualReview(eventId, { reason: reviewReason, operator: "王海峰" });
    setBusy(false);
    setModal(null);
    setStatus("人工复核中");
    showToast(result.mode !== "api" ? "模拟操作：事件已退回人工复核队列" : "事件已退回人工复核队列", "warning");
  };

  const handlePublish = async () => {
    const selectedChannels = Object.entries(channels).filter(([, enabled]) => enabled).map(([name]) => name);
    if (selectedChannels.length === 0) {
      showToast("至少选择一个发布渠道", "warning");
      return;
    }
    setBusy(true);
    const result = await publishWarning(eventId, {
      operator: "王海峰",
      channels: selectedChannels,
      action: "关闭北口道闸并发布绕行提示",
    });
    setBusy(false);
    setModal(null);
    setStatus("已发布");
    showToast(result.mode !== "api" ? "模拟操作：预警已发布，联动回执已写入审计链" : "预警发布成功，正在等待终端回执");
  };

  const demOption = useMemo(
    () => ({
      animationDuration: 0,
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(22, 32, 43, .94)",
        borderWidth: 0,
        textStyle: { color: "#fff" },
        formatter: (params) => {
          const ground = params.find((item) => item.seriesName === "路面高程");
          const water = params.find((item) => item.seriesName === "积水面");
          return `横向距离 ${params[0].axisValue}m<br/>路面高程 ${ground?.value ?? "—"}m<br/>积水面 ${water?.value ?? "—"}m`;
        },
      },
      grid: { left: 52, right: 24, top: 28, bottom: 38 },
      xAxis: {
        type: "category",
        name: "道路横向距离 / m",
        boundaryGap: false,
        data: ["-24", "-20", "-16", "-12", "-8", "-4", "0", "4", "8", "12", "16", "20", "24"],
        axisLabel: { color: "#85919d", fontSize: 10 },
        nameTextStyle: { color: "#85919d", fontSize: 10 },
        axisLine: { lineStyle: { color: "#d9dfe5" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        name: "高程 / m",
        min: 12.9,
        max: 14.2,
        interval: 0.3,
        axisLabel: { color: "#85919d", fontSize: 10 },
        nameTextStyle: { color: "#85919d", fontSize: 10 },
        splitLine: { lineStyle: { color: "#edf0f3" } },
      },
      series: [
        {
          name: "路面高程",
          type: "line",
          smooth: 0.28,
          symbol: "none",
          data: [13.89, 13.73, 13.58, 13.48, 13.38, 13.26, 13.16, 13.22, 13.34, 13.47, 13.62, 13.76, 13.95],
          lineStyle: { color: "#606d78", width: 2 },
          areaStyle: { color: "rgba(119, 131, 143, .12)" },
        },
        {
          name: "积水面",
          type: "line",
          connectNulls: false,
          symbol: "none",
          data: [null, null, null, 13.38, 13.38, 13.38, 13.38, 13.38, 13.38, 13.38, null, null, null],
          lineStyle: { color: "#1495d3", width: 2 },
          areaStyle: { color: "rgba(42, 171, 224, .28)" },
          markPoint: {
            symbol: "pin",
            symbolSize: 48,
            label: { color: "#fff", fontSize: 10, formatter: "最大\n22cm" },
            itemStyle: { color: "#167ab5" },
            data: [{ coord: [6, 13.38] }],
          },
        },
      ],
    }),
    [],
  );

  const forecastOption = useMemo(
    () => ({
      animationDuration: 0,
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(22, 32, 43, .94)",
        borderWidth: 0,
        textStyle: { color: "#fff" },
        formatter: (params) => {
          const forecast = params.find((item) => item.seriesName === "预测水深");
          return `${forecast.axisValue}<br/>预测水深 <b>${forecast.value} cm</b>`;
        },
      },
      grid: { left: 38, right: 14, top: 24, bottom: 32 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: ["当前", "+15分", "+30分", "+60分"],
        axisLabel: { color: "#7c8995", fontSize: 10 },
        axisLine: { lineStyle: { color: "#dde2e7" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 60,
        interval: 15,
        axisLabel: { color: "#7c8995", fontSize: 10 },
        splitLine: { lineStyle: { color: "#edf0f3" } },
      },
      series: [
        {
          name: "区间下界",
          type: "line",
          stack: "confidence-band",
          data: [20, 34, 44, 39],
          symbol: "none",
          silent: true,
          lineStyle: { opacity: 0 },
          areaStyle: { opacity: 0 },
          tooltip: { show: false },
        },
        {
          name: "不确定区间",
          type: "line",
          stack: "confidence-band",
          data: [4, 8, 12, 16],
          symbol: "none",
          silent: true,
          lineStyle: { opacity: 0 },
          areaStyle: { color: "rgba(71, 157, 217, .14)" },
          tooltip: { show: false },
        },
        {
          name: "预测水深",
          type: "line",
          smooth: 0.35,
          data: [22, 38, 51, 47],
          symbolSize: 7,
          lineStyle: { color: "#277cc2", width: 2.5 },
          itemStyle: { color: "#277cc2", borderColor: "#fff", borderWidth: 2 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(39, 124, 194, .24)" },
                { offset: 1, color: "rgba(39, 124, 194, .02)" },
              ],
            },
          },
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { color: "#f19a4a", type: "dashed" },
            label: { color: "#c87424", fontSize: 9, formatter: "管控线 35cm" },
            data: [{ yAxis: 35 }],
          },
        },
      ],
    }),
    [],
  );

  return (
    <div className="review-page">
      <header className="review-header">
        <div className="review-header-main">
          <button className="review-back-button" type="button" onClick={() => navigate("/events")} aria-label="返回事件列表">
            <ArrowLeft size={20} />
          </button>
          <div>
            <div className="review-title-line">
              <h1>事件研判 <span>· {eventId}</span></h1>
              <span className={`review-status review-status--${status}`}>{status}</span>
              <span className="demo-data-badge">模拟态势</span>
            </div>
            <p><MapPin size={15} weight="fill" />{reviewSite.name} · {reviewSite.district} · 下穿隧道场景</p>
          </div>
        </div>
        <div className="review-header-meta">
          <div><span>事件触发</span><strong>2026-07-10 14:20:06</strong></div>
          <div><span>数据更新</span><strong>14:32:18</strong></div>
          <button type="button" onClick={() => navigate("/audit")}><LockKey size={17} />审计编号 LOG-710-142006<CaretRight size={15} /></button>
        </div>
      </header>

      <main className="review-main">
        <div className="review-visual-column">
          <section className="review-section live-camera-section">
            <header className="review-section-header">
              <div><h2>实时画面</h2><span>CAM-YJ-017 · 1080p / 30fps</span></div>
              <span className="live-status"><i />实时</span>
            </header>
            <div className="camera-frame">
              <img src={assetPath("assets/tunnel-water-overlay.png")} alt="滨河路下穿隧道路面积水识别实时画面" />
              <div className="camera-top-overlay">
                <span><Camera size={15} weight="fill" />边端识别画面</span>
                <time>2026-07-10 14:32:18</time>
              </div>
              <div className="camera-detection-label camera-detection-label--water">
                <span>积水识别区域</span><strong>置信度 0.92</strong>
              </div>
              <div className="camera-depth-pin"><span>最大水深</span><strong>22<small>cm</small></strong></div>
              <div className="camera-scale"><span>0m</span><i /><span>10m</span></div>
            </div>
            <div className="camera-footnote">
              <span><i className="legend-swatch legend-swatch--water" />积水边界</span>
              <span><i className="legend-swatch legend-swatch--road" />有效路面</span>
              <span>有效像素率 82%</span>
              <button type="button" onClick={openRawEvidence}>查看识别详情<CaretRight size={14} /></button>
            </div>
          </section>

          <section className="review-section dem-section">
            <header className="review-section-header">
              <div><h2>路面高程与积水剖面</h2><span>DEM-017-20260701 · 基线年龄9天</span></div>
              <div className="review-legend"><span><i className="legend-line legend-line--ground" />路面高程</span><span><i className="legend-line legend-line--water" />积水面</span></div>
            </header>
            <ReactECharts className="dem-chart" option={demOption} style={{ height: 245, width: "100%" }} />
            <div className="dem-summary-strip">
              <span><strong>286㎡</strong>积水面积</span>
              <span><strong>42.7m³</strong>估算体积</span>
              <span><strong>1.1cm/min</strong>上涨斜率</span>
              <span className="dem-saturation"><Warning size={15} weight="fill" /><strong>排水饱和</strong></span>
            </div>
          </section>
        </div>

        <aside className="review-analysis-column">
          <section className="review-section prediction-section">
            <header className="review-section-header">
              <div><h2>积水演化预测</h2><span>规则引擎 + 案例检索 + 物理校验</span></div>
              <span className="prediction-risk-badge"><CloudRain size={16} weight="fill" />强降雨</span>
            </header>
            <div className="prediction-kpis">
              <article className="prediction-kpi prediction-kpi--time"><span>预计达35cm</span><strong>12<small>分钟</small></strong><em>较上一轮提前3分钟</em></article>
              <article className="prediction-kpi"><span>当前最大水深</span><strong>22<small>cm</small></strong><em><TrendUp size={13} />持续上涨</em></article>
              <article className="prediction-kpi"><span>预报置信度</span><strong>88<small>%</small></strong><em>高置信</em></article>
            </div>
            <div className="risk-callout">
              <Warning size={20} weight="fill" />
              <div><strong>橙色预警 · 建议立即管控</strong><span>未来15分钟预计达到38cm，已超过小型车辆安全通行阈值。</span></div>
            </div>
            <ReactECharts className="prediction-chart" option={forecastOption} style={{ height: 220, width: "100%" }} />
            <div className="forecast-values">
              <span><i />当前<strong>22 cm</strong></span>
              <span><i />15分钟<strong>38 cm</strong></span>
              <span><i />30分钟<strong>51 cm</strong></span>
              <span><i />60分钟<strong>47 cm</strong></span>
            </div>
          </section>

          <section className="review-section evidence-section">
            <header className="review-section-header">
              <div><h2>研判依据链</h2><span>四层结果可反向审计</span></div>
              <button type="button" onClick={() => navigate("/audit")}>完整证据链<CaretRight size={14} /></button>
            </header>
            <ol className="evidence-steps">
              {evidenceSteps.map((step) => (
                <li className={`evidence-step evidence-step--${step.tone}`} key={step.id}>
                  <span className="evidence-index">{step.id}</span>
                  <div className="evidence-content">
                    <div><strong>{step.title}</strong><time>{step.time}</time></div>
                    <p>{step.summary}</p>
                    <span>{step.detail}</span>
                  </div>
                  <CheckCircle size={18} weight="fill" />
                </li>
              ))}
            </ol>
            <div className="evidence-hash"><ShieldCheck size={17} weight="fill" /><span>本次研判已生成加密摘要</span><code>00e7be82…fe23</code></div>
          </section>
        </aside>
      </main>

      <footer className="review-action-bar">
        <div className="review-operator">
          <UserCircle size={34} weight="fill" />
          <div><span>当前研判人</span><strong>王海峰 · 防汛值班长</strong></div>
        </div>
        <div className="review-action-context">
          <span><MapPin size={16} weight="fill" />{reviewSite.name}</span>
          <span><Clock size={16} />处置黄金窗口剩余 <strong>12分钟</strong></span>
        </div>
        <div className="review-actions">
          <button className="button button-secondary" type="button" onClick={openRawEvidence}><Database size={17} />查看原始数据</button>
          <button className="button button-secondary" type="button" onClick={() => setModal("review")} disabled={status === "已发布"}><ArrowCounterClockwise size={17} />退回人工复核</button>
          <button className="button button-publish" type="button" onClick={() => setModal("publish")} disabled={status === "已发布"}>
            {status === "已发布" ? <CheckCircle size={18} weight="fill" /> : <PaperPlaneTilt size={18} weight="fill" />}
            {status === "已发布" ? "预警已发布" : "确认预警并发布"}
          </button>
        </div>
      </footer>

      {modal && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !busy && setModal(null)}>
          <section className={`dialog dialog--${modal}`} role="dialog" aria-modal="true" aria-labelledby="dialog-title">
            <header className="dialog-header">
              <div>
                <span className="dialog-icon">
                  {modal === "raw" ? <Database size={22} /> : modal === "review" ? <ArrowCounterClockwise size={22} /> : <Broadcast size={22} />}
                </span>
                <div>
                  <h2 id="dialog-title">{modal === "raw" ? "原始数据与证据快照" : modal === "review" ? "退回人工复核" : "确认预警并发布"}</h2>
                  <p>{eventId} · {reviewSite.name}</p>
                </div>
              </div>
              <button type="button" onClick={() => !busy && setModal(null)} aria-label="关闭"><X size={20} /></button>
            </header>

            {modal === "raw" && (
              <div className="dialog-body raw-evidence-dialog">
                {busy && <div className="dialog-loading"><span />正在读取原始证据…</div>}
                {!busy && rawEvidence && (
                  <>
                    <div className="raw-preview">
                      <img src={assetPath("assets/tunnel-water-overlay.png")} alt="原始识别关键帧" />
                      <span>{rawEvidence.frameId}</span>
                    </div>
                    <dl className="raw-data-grid">
                      <div><dt>采集时间</dt><dd>{rawEvidence.capturedAt}</dd></div>
                      <div><dt>图像质量</dt><dd>{rawEvidence.imageQuality}%</dd></div>
                      <div><dt>有效像素率</dt><dd>{rawEvidence.effectivePixels}%</dd></div>
                      <div><dt>边界 IoU</dt><dd>{rawEvidence.boundaryIou}</dd></div>
                      <div><dt>DEM版本</dt><dd>{rawEvidence.demVersion}</dd></div>
                      <div><dt>综合可信度</dt><dd>{rawEvidence.confidence}%</dd></div>
                    </dl>
                    <div className="raw-checksum"><LockKey size={16} /><div><span>数据校验摘要</span><code>{rawEvidence.checksum}</code></div></div>
                  </>
                )}
              </div>
            )}

            {modal === "review" && (
              <div className="dialog-body">
                <div className="dialog-warning"><Info size={20} weight="fill" /><p>退回后事件将进入人工复核队列，自动联动暂停，但实时监测与数据存证仍会继续。</p></div>
                <label className="dialog-field">
                  <span>复核原因</span>
                  <textarea rows="4" value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} />
                </label>
                <label className="dialog-field"><span>指派队列</span><select defaultValue="防汛人工复核队列"><option>防汛人工复核队列</option><option>市政养护复核队列</option></select></label>
              </div>
            )}

            {modal === "publish" && (
              <div className="dialog-body publish-dialog">
                <div className="publish-summary">
                  <Warning size={24} weight="fill" />
                  <div><span>橙色预警</span><strong>预计12分钟后积水达到35厘米</strong><p>建议立即关闭隧道北口，并向车辆发布绕行提示。</p></div>
                </div>
                <fieldset className="channel-options">
                  <legend>选择发布与联动渠道</legend>
                  {[
                    ["gate", "北口道闸", "发送关闭指令并等待设备回执"],
                    ["led", "道路LED诱导屏", "发布前方积水、车辆绕行信息"],
                    ["app", "管理人员APP", "推送预警、预测曲线和处置建议"],
                    ["patrol", "现场巡查任务", "指派最近巡查人员到场核验"],
                  ].map(([key, title, description]) => (
                    <label className="channel-option" key={key}>
                      <input type="checkbox" checked={channels[key]} onChange={(event) => setChannels((current) => ({ ...current, [key]: event.target.checked }))} />
                      <span><CheckCircle size={19} weight="fill" /></span>
                      <div><strong>{title}</strong><small>{description}</small></div>
                    </label>
                  ))}
                </fieldset>
                <div className="publish-audit-note"><ShieldCheck size={18} weight="fill" /><span>确认后将记录操作人、发布时间、渠道回执和研判数据快照。</span></div>
              </div>
            )}

            <footer className="dialog-footer">
              {modal === "raw" ? (
                <>
                  <button className="button button-secondary" type="button" onClick={() => navigate("/audit")}><FileText size={17} />查看完整证据链</button>
                  <button className="button button-primary" type="button" onClick={() => setModal(null)}>关闭</button>
                </>
              ) : (
                <>
                  <button className="button button-secondary" type="button" onClick={() => setModal(null)} disabled={busy}>取消</button>
                  <button className={modal === "publish" ? "button button-publish" : "button button-primary"} type="button" onClick={modal === "publish" ? handlePublish : handleManualReview} disabled={busy || (modal === "review" && !reviewReason.trim())}>
                    {busy ? "正在提交…" : modal === "publish" ? "确认发布" : "确认退回复核"}
                  </button>
                </>
              )}
            </footer>
          </section>
        </div>
      )}

      {toast && (
        <div className={`toast toast--${toast.tone}`} role="status" aria-live="polite">
          {toast.tone === "success" ? <CheckCircle size={20} weight="fill" /> : <Warning size={20} weight="fill" />}
          <span>{toast.message}</span>
          <button type="button" onClick={() => setToast(null)} aria-label="关闭提示"><X size={16} /></button>
        </div>
      )}
    </div>
  );
}

export default ReviewPage;
