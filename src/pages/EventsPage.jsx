import { useMemo, useState } from "react";
import {
  Archive,
  BellRinging,
  CaretRight,
  Check,
  CheckCircle,
  ClockCountdown,
  Funnel,
  MagnifyingGlass,
  PaperPlaneTilt,
  ShieldCheck,
  UserSwitch,
  Warning,
} from "@phosphor-icons/react";
import { useLocation } from "react-router-dom";
import { eventsData, filterOptions } from "../data/demoData";

const severityOptions = [
  { value: "all", label: "全部等级" },
  { value: "critical", label: "红色预警" },
  { value: "high", label: "橙色预警" },
  { value: "medium", label: "黄色关注" },
];

const assignees = ["王海峰", "赵清", "陈晓楠", "李锐"];

const nextActions = {
  待确认: { label: "确认并接管", next: "处置中", icon: Check },
  处置中: { label: "转入持续观察", next: "持续观察", icon: ShieldCheck },
  持续观察: { label: "确认风险解除", next: "已恢复", icon: CheckCircle },
  已恢复: { label: "完成事件归档", next: "已归档", icon: Archive },
};

export function EventsPage({ initialSiteId }) {
  const location = useLocation();
  const routedSiteId = typeof location.state?.siteId === "string" ? location.state.siteId : null;
  const requestedSiteId = initialSiteId ?? routedSiteId;
  const matchedInitialEvent = eventsData.find((item) => item.siteId === requestedSiteId);
  const initialEvent = matchedInitialEvent ?? eventsData[0];
  const [events, setEvents] = useState(eventsData);
  const [selectedId, setSelectedId] = useState(initialEvent.id);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");
  const [status, setStatus] = useState("全部状态");
  const [assignee, setAssignee] = useState(initialEvent.assignee === "未指派" ? assignees[0] : initialEvent.assignee);
  const [notice, setNotice] = useState(
    requestedSiteId && !matchedInitialEvent
      ? "所选点位暂无关联事件，已展示全部处置队列。"
      : "按距达险时间排序，红色事件优先处置。",
  );

  const filteredEvents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return events
      .filter((event) => {
        const matchesQuery =
          !normalizedQuery ||
          event.siteName.toLowerCase().includes(normalizedQuery) ||
          event.id.toLowerCase().includes(normalizedQuery) ||
          event.assignee.toLowerCase().includes(normalizedQuery);
        const matchesSeverity = severity === "all" || event.severity === severity;
        const matchesStatus = status === "全部状态" || event.status === status;
        return matchesQuery && matchesSeverity && matchesStatus;
      })
      .sort((a, b) => (a.eta ?? 999) - (b.eta ?? 999));
  }, [events, query, severity, status]);

  const activeEvent = events.find((event) => event.id === selectedId) ?? filteredEvents[0] ?? events[0];
  const transition = nextActions[activeEvent.status];
  const TransitionIcon = transition?.icon ?? CheckCircle;

  const updateActiveEvent = (updater) => {
    setEvents((current) => current.map((event) => (event.id === activeEvent.id ? updater(event) : event)));
  };

  const handleTransition = () => {
    if (!transition) return;
    updateActiveEvent((event) => ({
      ...event,
      status: transition.next,
      assignee: event.assignee === "未指派" ? assignee : event.assignee,
      timeline: [
        ...event.timeline,
        {
          time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
          title: transition.label,
          detail: `模拟操作：事件状态已更新为“${transition.next}”。`,
          tone: "success",
        },
      ],
    }));
    setNotice(`操作成功：${activeEvent.id} 已更新为“${transition.next}”。`);
  };

  const handleAssign = () => {
    updateActiveEvent((event) => ({ ...event, assignee }));
    setNotice(`已将 ${activeEvent.id} 指派给 ${assignee}。`);
  };

  const handleDispatch = () => {
    updateActiveEvent((event) => ({
      ...event,
      status: event.status === "待确认" ? "处置中" : event.status,
      assignee: event.assignee === "未指派" ? assignee : event.assignee,
      commands: event.commands.map((command) =>
        command.status === "待执行"
          ? {
              ...command,
              status: "已送达",
              time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
            }
          : command,
      ),
    }));
    setNotice(`已下发 ${activeEvent.commands.length} 项处置指令，正在等待终端回执。`);
  };

  return (
    <div className="subpage events-page" data-page="events">
      <header className="page-header">
        <div className="page-heading">
          <div className="page-eyebrow">
            <BellRinging size={16} weight="fill" />
            预警处置
          </div>
          <h1>事件指挥中心</h1>
          <p>从预警签收到恢复归档，全流程记录责任、指令、回执与证据。</p>
        </div>
        <div className="page-header-actions">
          <span className="demo-data-badge">模拟处置流程</span>
          <button className="button button-secondary" type="button" onClick={() => setNotice("已发起全量事件状态同步。")}>
            同步处置状态
          </button>
          <button className="button button-primary" type="button" onClick={() => setNotice("已创建一条人工上报草稿，可补充现场证据。")}>
            + 人工上报
          </button>
        </div>
      </header>

      <div className="operation-notice" role="status" aria-live="polite">
        <ShieldCheck size={18} weight="fill" />
        <span>{notice}</span>
      </div>

      <section className="filter-bar" aria-label="事件筛选">
        <div className="filter-bar-title"><Funnel size={17} />筛选</div>
        <label className="search-field">
          <MagnifyingGlass size={17} />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索事件、点位或责任人"
          />
        </label>
        <label className="field-inline">
          <span>等级</span>
          <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
            {severityOptions.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="field-inline">
          <span>状态</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {filterOptions.eventStatuses.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <span className="filter-result-count">共 {filteredEvents.length} 条</span>
      </section>

      <div className="events-workspace">
        <section className="panel event-list-panel" aria-label="预警事件列表">
          <header className="panel-header">
            <div>
              <h2>处置队列</h2>
              <p>红色事件优先，队列按达险时间排序</p>
            </div>
            <span className="count-badge">{filteredEvents.length}</span>
          </header>

          <div className="event-list" role="list">
            {filteredEvents.map((event) => (
              <button
                className={`event-list-item event-list-item--${event.severity} ${activeEvent.id === event.id ? "is-selected" : ""}`}
                type="button"
                key={event.id}
                onClick={() => {
                  setSelectedId(event.id);
                  setAssignee(event.assignee === "未指派" ? assignees[0] : event.assignee);
                }}
                role="listitem"
              >
                <span className={`severity-rail severity-rail--${event.severity}`} />
                <span className="event-item-main">
                  <span className="event-item-title-row">
                    <strong>{event.siteName}</strong>
                    <span className={`status-badge status-badge--${event.severity}`}>{event.severityLabel}</span>
                  </span>
                  <span className="event-item-meta">{event.id} · {event.district}</span>
                  <span className="event-item-readings">
                    <span>当前 <b>{event.currentDepth}cm</b></span>
                    <span>{event.forecastHorizon}分钟 <b>{event.forecastDepth}cm</b></span>
                    <span>置信度 <b>{event.confidence}%</b></span>
                  </span>
                </span>
                <span className="event-item-side">
                  <span className={`workflow-status workflow-status--${event.status}`}>{event.status}</span>
                  <span className="eta-label">
                    <ClockCountdown size={15} />
                    {event.eta ? `${event.eta}分钟达险` : "风险已解除"}
                  </span>
                  <span>{event.assignee}</span>
                </span>
                <CaretRight size={17} />
              </button>
            ))}
            {filteredEvents.length === 0 && (
              <div className="empty-state">
                <BellRinging size={28} />
                <strong>没有匹配的事件</strong>
                <span>请清除关键词或调整筛选条件。</span>
              </div>
            )}
          </div>
        </section>

        <section className="panel event-detail-panel" aria-label="事件详情">
          <header className="event-detail-header">
            <div>
              <div className="site-title-line">
                <span className={`status-badge status-badge--${activeEvent.severity}`}>{activeEvent.severityLabel}预警</span>
                <span className={`workflow-status workflow-status--${activeEvent.status}`}>{activeEvent.status}</span>
              </div>
              <h2>{activeEvent.siteName}</h2>
              <p>{activeEvent.id} · 触发于 {activeEvent.triggerAt} · 最近更新 {activeEvent.updatedAt}</p>
            </div>
            <div className="event-sla-block">
              <span>SLA 剩余</span>
              <strong>{activeEvent.sla}</strong>
            </div>
          </header>

          <div className="event-detail-body">
            <div className="event-decision-summary">
              <article className="decision-reading decision-reading--primary">
                <span>当前水深</span>
                <strong>{activeEvent.currentDepth}<small>cm</small></strong>
              </article>
              <article className="decision-reading">
                <span>{activeEvent.forecastHorizon}分钟预测</span>
                <strong>{activeEvent.forecastDepth}<small>cm</small></strong>
              </article>
              <article className="decision-reading">
                <span>预计达险</span>
                <strong>{activeEvent.eta ?? "—"}<small>{activeEvent.eta ? "分钟" : ""}</small></strong>
              </article>
              <article className="decision-reading">
                <span>预报置信度</span>
                <strong>{activeEvent.confidence}<small>%</small></strong>
              </article>
            </div>

            <section className="decision-recommendation" aria-label="系统建议">
              <div className="decision-recommendation-icon"><Warning size={22} weight="fill" /></div>
              <div>
                <span>系统建议 · {activeEvent.source}</span>
                <p>{activeEvent.recommendation}</p>
              </div>
            </section>

            <div className="event-action-bar">
              <label className="assignee-control">
                <span>责任人</span>
                <select value={assignee} onChange={(event) => setAssignee(event.target.value)}>
                  {assignees.map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
              <button className="button button-secondary" type="button" onClick={handleAssign}>
                <UserSwitch size={17} />
                指派
              </button>
              <button className="button button-secondary" type="button" onClick={handleDispatch} disabled={activeEvent.status === "已归档"}>
                <PaperPlaneTilt size={17} weight="fill" />
                一键下发建议
              </button>
              <button className="button button-primary" type="button" onClick={handleTransition} disabled={!transition}>
                <TransitionIcon size={17} weight="bold" />
                {transition?.label ?? "事件已归档"}
              </button>
            </div>

            <div className="event-detail-columns">
              <section className="event-section command-section">
                <header>
                  <div>
                    <h3>处置指令</h3>
                    <p>指令、终端回执和执行结果同步记录</p>
                  </div>
                  <span>{activeEvent.commands.filter((item) => item.status !== "待执行").length}/{activeEvent.commands.length}</span>
                </header>
                <div className="command-list">
                  {activeEvent.commands.map((command) => (
                    <div className="command-row" key={command.id}>
                      <span className={`command-state command-state--${command.status}`}>
                        {command.status === "已执行" ? <CheckCircle size={18} weight="fill" /> : <span />}
                      </span>
                      <div>
                        <strong>{command.label}</strong>
                        <span>{command.time}</span>
                      </div>
                      <em>{command.status}</em>
                    </div>
                  ))}
                </div>
              </section>

              <section className="event-section timeline-section">
                <header>
                  <div>
                    <h3>处置时间线</h3>
                    <p>所有节点写入防篡改审计链</p>
                  </div>
                  <ShieldCheck size={20} weight="fill" />
                </header>
                <ol className="event-timeline">
                  {[...activeEvent.timeline].reverse().map((item, index) => (
                    <li className={`timeline-item timeline-item--${item.tone}`} key={`${item.time}-${index}`}>
                      <span className="timeline-marker" />
                      <time>{item.time}</time>
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.detail}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default EventsPage;
