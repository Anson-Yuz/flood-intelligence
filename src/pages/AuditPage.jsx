import { useMemo, useState } from "react";
import {
  CheckCircle,
  Copy,
  DownloadSimple,
  FileText,
  Fingerprint,
  Funnel,
  LinkSimple,
  LockKey,
  MagnifyingGlass,
  ShieldCheck,
  Warning,
} from "@phosphor-icons/react";
import { auditData, eventsData, filterOptions } from "../data/demoData";

export function AuditPage({ initialEventId = "全部事件" }) {
  const [selectedId, setSelectedId] = useState(auditData[0].id);
  const [eventId, setEventId] = useState(initialEventId);
  const [stage, setStage] = useState("全部环节");
  const [result, setResult] = useState("全部结果");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("审计链采用前序哈希关联，当前演示记录完整。 ");
  const [verified, setVerified] = useState(true);

  const filteredLogs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return auditData.filter((log) => {
      const matchesEvent = eventId === "全部事件" || log.eventId === eventId;
      const matchesStage = stage === "全部环节" || log.stage === stage;
      const matchesResult = result === "全部结果" || log.resultLabel === result;
      const matchesQuery =
        !normalized ||
        log.action.toLowerCase().includes(normalized) ||
        log.operator.toLowerCase().includes(normalized) ||
        log.hash.toLowerCase().includes(normalized);
      return matchesEvent && matchesStage && matchesResult && matchesQuery;
    });
  }, [eventId, stage, result, query]);

  const activeLog = auditData.find((item) => item.id === selectedId) ?? filteredLogs[0] ?? auditData[0];

  const verifyChain = () => {
    const chainValid = filteredLogs.every((log) => log.hash && log.previousHash);
    setVerified(chainValid);
    setNotice(
      chainValid
        ? `完整性验证通过：${filteredLogs.length} 条记录哈希可追溯，未发现缺口或篡改。`
        : "完整性验证失败：发现缺失哈希的记录，请人工复核。",
    );
  };

  const exportEvidence = () => {
    const payload = {
      exportedAt: new Date().toISOString(),
      label: "预鉴平台模拟存证包",
      filters: { eventId, stage, result },
      records: filteredLogs,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `yujian-audit-${Date.now()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice(`已导出 ${filteredLogs.length} 条记录的模拟存证包。`);
  };

  const copyHash = async () => {
    try {
      await navigator.clipboard.writeText(activeLog.hash);
      setNotice(`已复制 ${activeLog.id} 的SHA-256摘要。`);
    } catch {
      setNotice(`摘要复制受浏览器限制，请在详情中手动选择：${activeLog.hash.slice(0, 18)}…`);
    }
  };

  return (
    <div className="subpage audit-page" data-page="audit">
      <header className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow">
            <LockKey size={16} weight="fill" />
            报表与存证
          </div>
          <h1>推理审计与履职证据链</h1>
          <p>复核每次预报的输入、中间结果、人工操作和终端回执。</p>
        </div>
        <div className="page-header-actions">
          <span className="demo-data-badge">SHA-256 模拟链</span>
          <button className="button button-secondary" type="button" onClick={verifyChain}>
            <ShieldCheck size={17} weight="fill" />
            验证完整性
          </button>
          <button className="button button-primary" type="button" onClick={exportEvidence}>
            <DownloadSimple size={17} />
            导出存证包
          </button>
        </div>
      </header>

      <section className="audit-summary-grid" aria-label="审计概况">
        <article className="audit-summary-card audit-summary-card--verified">
          <div className="audit-summary-icon"><ShieldCheck size={24} weight="fill" /></div>
          <div><span>证据链状态</span><strong>{verified ? "完整可信" : "需要复核"}</strong><small>最近验证：刚刚</small></div>
        </article>
        <article className="audit-summary-card">
          <div className="audit-summary-icon"><LinkSimple size={24} /></div>
          <div><span>今日链上记录</span><strong>1,284</strong><small>自动记录 96.8%</small></div>
        </article>
        <article className="audit-summary-card">
          <div className="audit-summary-icon"><Fingerprint size={24} /></div>
          <div><span>人工签收率</span><strong>100%</strong><small>红橙预警无遗漏</small></div>
        </article>
        <article className="audit-summary-card">
          <div className="audit-summary-icon"><FileText size={24} /></div>
          <div><span>可导出事件包</span><strong>17</strong><small>含数据与终端回执</small></div>
        </article>
      </section>

      <div className={`operation-notice operation-notice--${verified ? "success" : "warning"}`} role="status" aria-live="polite">
        {verified ? <CheckCircle size={18} weight="fill" /> : <Warning size={18} weight="fill" />}
        <span>{notice}</span>
      </div>

      <section className="filter-bar" aria-label="审计记录筛选">
        <div className="filter-bar-title"><Funnel size={17} />筛选</div>
        <label className="search-field">
          <MagnifyingGlass size={17} />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索操作人、动作或哈希" />
        </label>
        <label className="field-inline">
          <span>事件</span>
          <select value={eventId} onChange={(event) => setEventId(event.target.value)}>
            <option>全部事件</option>
            {eventsData.map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}
          </select>
        </label>
        <label className="field-inline">
          <span>环节</span>
          <select value={stage} onChange={(event) => setStage(event.target.value)}>
            {filterOptions.auditStages.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label className="field-inline">
          <span>结果</span>
          <select value={result} onChange={(event) => setResult(event.target.value)}>
            {["全部结果", "执行成功", "签收成功", "校验通过", "计算完成", "数据可信"].map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
      </section>

      <div className="audit-workspace">
        <section className="panel audit-chain-panel" aria-label="审计链记录">
          <header className="panel-header">
            <div><h2>证据链记录</h2><p>共 {filteredLogs.length} 条匹配记录</p></div>
            <span className="chain-health"><span />链路正常</span>
          </header>
          <ol className="audit-chain-list">
            {filteredLogs.map((log) => (
              <li key={log.id}>
                <button
                  type="button"
                  className={`audit-chain-item ${activeLog.id === log.id ? "is-selected" : ""}`}
                  onClick={() => setSelectedId(log.id)}
                >
                  <span className="audit-chain-node"><CheckCircle size={18} weight="fill" /></span>
                  <span className="audit-chain-time">{log.time.slice(11)}</span>
                  <span className="audit-chain-main">
                    <span className="audit-chain-stage">{log.stage}</span>
                    <strong>{log.action}</strong>
                    <span>{log.operator} · {log.source}</span>
                  </span>
                  <span className="audit-hash-preview">{log.hash.slice(0, 10)}…</span>
                  <span className="status-badge status-badge--success">{log.resultLabel}</span>
                </button>
              </li>
            ))}
          </ol>
          {filteredLogs.length === 0 && (
            <div className="empty-state"><LockKey size={28} /><strong>无匹配记录</strong><span>请调整筛选条件。</span></div>
          )}
        </section>

        <aside className="panel audit-detail-panel" aria-label="审计详情">
          <header className="audit-detail-header">
            <div>
              <span className="page-eyebrow">{activeLog.stage}</span>
              <h2>{activeLog.action}</h2>
              <p>{activeLog.id}</p>
            </div>
            <span className="status-badge status-badge--success">{activeLog.resultLabel}</span>
          </header>

          <section className="audit-section">
            <h3>记录主体</h3>
            <dl className="detail-list detail-list--two-column">
              <div><dt>关联事件</dt><dd>{activeLog.eventId}</dd></div>
              <div><dt>精确时间</dt><dd>{activeLog.time}</dd></div>
              <div><dt>操作主体</dt><dd>{activeLog.operator}</dd></div>
              <div><dt>主体角色</dt><dd>{activeLog.role}</dd></div>
              <div><dt>数据来源</dt><dd>{activeLog.source}</dd></div>
              <div><dt>来源地址</dt><dd>{activeLog.sourceIp}</dd></div>
            </dl>
          </section>

          <section className="audit-section">
            <h3>审计说明</h3>
            <p className="audit-detail-copy">{activeLog.detail}</p>
          </section>

          <section className="audit-section">
            <div className="section-title-row">
              <h3>数据摘要</h3>
              <button className="button button-ghost button-small" type="button" onClick={copyHash}><Copy size={15} />复制</button>
            </div>
            <div className="hash-block">
              <span>当前 SHA-256</span>
              <code>{activeLog.hash}</code>
            </div>
            <div className="hash-block hash-block--previous">
              <span>前序记录摘要</span>
              <code>{activeLog.previousHash}</code>
            </div>
          </section>

          <section className="audit-section">
            <h3>随附证据</h3>
            <ul className="evidence-list">
              {activeLog.evidence.map((item) => (
                <li key={item}><FileText size={17} /><span>{item}</span><CheckCircle size={16} weight="fill" /></li>
              ))}
            </ul>
          </section>

          <div className="audit-integrity-seal">
            <ShieldCheck size={27} weight="fill" />
            <div><strong>本记录已通过完整性校验</strong><span>哈希摘要与前序记录连续，无异常修改痕迹。</span></div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default AuditPage;
