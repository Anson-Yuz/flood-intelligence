from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .audit import append_audit, verify_audit_chain
from .auth import require_session_user, resolve_session
from .database import get_db
from .inference import create_forecast_run
from .models import (
    ActionRecord,
    Alert,
    AuditLog,
    Device,
    ForecastRun,
    InferenceStep,
    ScenarioRun,
    Site,
    WaterState,
    WeatherSnapshot,
    utcnow,
)
from .schemas import (
    ActionDecision,
    ActionRead,
    AlertRead,
    AuditLogRead,
    DeviceRead,
    EdgeCommandAck,
    EdgeHeartbeat,
    EdgeTelemetryEnvelope,
    EdgeUnifiedEnvelope,
    ForecastRunRead,
    InferenceStepRead,
    ReviewDetail,
    ScenarioRunRead,
    ScenarioStartRequest,
    SiteDetail,
    SiteSummary,
    WaterStateRead,
    WeatherRead,
)
from .simulator import ScenarioManager, ScenarioNotFoundError


router = APIRouter(dependencies=[Depends(require_session_user)])
public_router = APIRouter()
# TODO: replace this public edge router with per-device credentials/signatures
# before exposing hardware ingestion or command polling outside the trusted LAN.
edge_router = APIRouter(prefix="/edge/v1", tags=["edge"])
SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _dump(schema_type: type[SchemaT], value: Any) -> dict[str, Any]:
    return schema_type.model_validate(value).model_dump(by_alias=True, mode="json")


def _latest_water(db: Session, site_id: str) -> WaterState | None:
    return db.scalar(
        select(WaterState)
        .where(WaterState.site_id == site_id)
        .order_by(WaterState.observed_at.desc(), WaterState.id.desc())
        .limit(1)
    )


def _latest_weather(db: Session, site_id: str) -> WeatherSnapshot | None:
    return db.scalar(
        select(WeatherSnapshot)
        .where(WeatherSnapshot.site_id == site_id)
        .order_by(WeatherSnapshot.observed_at.desc(), WeatherSnapshot.id.desc())
        .limit(1)
    )


def _latest_forecast(db: Session, site_id: str) -> ForecastRun | None:
    return db.scalar(
        select(ForecastRun)
        .options(selectinload(ForecastRun.points))
        .where(ForecastRun.site_id == site_id, ForecastRun.is_current.is_(True))
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    )


def _site_summary(db: Session, site: Site) -> SiteSummary:
    latest_water = _latest_water(db, site.id)
    latest_weather = _latest_weather(db, site.id)
    latest_forecast = _latest_forecast(db, site.id)
    active_alert_count = db.scalar(
        select(func.count())
        .select_from(Alert)
        .where(Alert.site_id == site.id, Alert.status.in_(["open", "acknowledged", "escalated"]))
    ) or 0
    device_count = db.scalar(
        select(func.count()).select_from(Device).where(Device.site_id == site.id)
    ) or 0
    online_device_count = db.scalar(
        select(func.count())
        .select_from(Device)
        .where(Device.site_id == site.id, Device.status == "online")
    ) or 0
    return SiteSummary(
        id=site.id,
        name=site.name,
        short_name=site.short_name,
        site_type=site.site_type,
        district=site.district,
        address=site.address,
        latitude=site.latitude,
        longitude=site.longitude,
        coverage_area_m2=site.coverage_area_m2,
        status=site.status,
        current_mode=site.current_mode,
        risk_level=site.risk_level,
        risk_threshold_cm=site.risk_threshold_cm,
        closure_threshold_cm=site.closure_threshold_cm,
        latest_water=WaterStateRead.model_validate(latest_water) if latest_water else None,
        latest_weather=WeatherRead.model_validate(latest_weather) if latest_weather else None,
        latest_forecast=ForecastRunRead.model_validate(latest_forecast) if latest_forecast else None,
        active_alert_count=active_alert_count,
        online_device_count=online_device_count,
        device_count=device_count,
    )


def _event_timeline(db: Session, limit: int = 20, site_id: str | None = None) -> list[dict[str, Any]]:
    alert_stmt = select(Alert).order_by(Alert.updated_at.desc()).limit(limit)
    action_stmt = select(ActionRecord).order_by(ActionRecord.requested_at.desc()).limit(limit)
    audit_stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit)
    if site_id:
        alert_stmt = alert_stmt.where(Alert.site_id == site_id)
        action_stmt = action_stmt.where(ActionRecord.site_id == site_id)
        audit_stmt = audit_stmt.where(AuditLog.site_id == site_id)
    alerts = list(db.scalars(alert_stmt))
    actions = list(db.scalars(action_stmt))
    audits = list(db.scalars(audit_stmt))
    site_names = {site.id: site.short_name for site in db.scalars(select(Site))}
    events: list[dict[str, Any]] = []
    for alert in alerts:
        events.append(
            {
                "id": alert.id,
                "type": "alert",
                "time": alert.updated_at,
                "siteId": alert.site_id,
                "siteName": site_names.get(alert.site_id, alert.site_id),
                "level": alert.level,
                "status": alert.status,
                "title": alert.title,
                "message": alert.message,
                "resourceId": alert.forecast_run_id,
            }
        )
    for action in actions:
        events.append(
            {
                "id": action.id,
                "type": "action",
                "time": action.requested_at,
                "siteId": action.site_id,
                "siteName": site_names.get(action.site_id, action.site_id),
                "level": action.priority,
                "status": action.status,
                "title": f"{action.action_type} · {action.target_id}",
                "message": action.decision_reason or "等待值班人员复核",
                "resourceId": action.alert_id,
            }
        )
    for audit in audits:
        events.append(
            {
                "id": f"audit-{audit.id}",
                "type": "audit",
                "time": audit.occurred_at,
                "siteId": audit.site_id,
                "siteName": site_names.get(audit.site_id or "", "全局"),
                "level": "info",
                "status": "sealed",
                "title": audit.action,
                "message": f"{audit.actor_id} · {audit.resource_type}",
                "resourceId": audit.resource_id,
            }
        )
    events.sort(key=lambda item: item["time"], reverse=True)
    return events[:limit]


@public_router.get("/health", tags=["system"])
def health(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    db.execute(select(1))
    site_count = db.scalar(select(func.count()).select_from(Site)) or 0
    return {
        "status": "ok",
        "service": request.app.state.settings.app_name,
        "version": request.app.state.settings.app_version,
        "database": request.app.state.settings.database_url.split(":", 1)[0],
        "seeded": site_count >= 4,
        "timestamp": utcnow(),
    }


@router.get("/dashboard", tags=["dashboard"])
@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    sites = list(db.scalars(select(Site).order_by(Site.sort_order.asc(), Site.name.asc())))
    summaries = [_site_summary(db, site) for site in sites]
    primary = next((item for item in summaries if item.id == "site-binh-rd-tunnel"), summaries[0])
    active_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.status.in_(["open", "acknowledged", "escalated"]))
    ) or 0
    pending_actions = db.scalar(
        select(func.count()).select_from(ActionRecord).where(ActionRecord.status == "pending")
    ) or 0
    online_devices = db.scalar(
        select(func.count()).select_from(Device).where(Device.status == "online")
    ) or 0
    total_devices = db.scalar(select(func.count()).select_from(Device)) or 0
    max_depth = max(
        (item.latest_water.max_depth_cm for item in summaries if item.latest_water),
        default=0.0,
    )
    forecast_curve = []
    if primary.latest_forecast:
        forecast_curve = [
            {
                "minute": point.horizon_minutes,
                "depthCm": point.predicted_depth_cm,
                "lowerCm": point.lower_depth_cm,
                "upperCm": point.upper_depth_cm,
                "riskLevel": point.risk_level,
            }
            for point in primary.latest_forecast.points
        ]
    return {
        "generatedAt": utcnow(),
        "tenant": {"id": "demo-tenant", "name": "杭州市城市生命线运行中心（演示）"},
        "overview": {
            "siteCount": len(sites),
            "onlineSiteCount": sum(1 for site in sites if site.status == "online"),
            "activeAlertCount": active_alerts,
            "pendingActionCount": pending_actions,
            "onlineDeviceCount": online_devices,
            "deviceCount": total_devices,
            "maxDepthCm": round(max_depth, 1),
        },
        "primarySite": primary.model_dump(by_alias=True, mode="json"),
        "sites": [item.model_dump(by_alias=True, mode="json") for item in summaries],
        "forecastCurve": forecast_curve,
        "events": _event_timeline(db, limit=12),
    }


@router.get("/sites", tags=["sites"])
def list_sites(
    risk_level: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(Site).order_by(Site.sort_order.asc(), Site.name.asc())
    if risk_level:
        stmt = stmt.where(Site.risk_level == risk_level)
    if status_filter:
        stmt = stmt.where(Site.status == status_filter)
    return [
        item.model_dump(by_alias=True, mode="json")
        for item in (_site_summary(db, site) for site in db.scalars(stmt))
    ]


@router.get("/sites/{site_id}", tags=["sites"])
def get_site(site_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    site = db.scalar(
        select(Site).options(selectinload(Site.devices)).where(Site.id == site_id)
    )
    if site is None:
        raise HTTPException(status_code=404, detail="监测点不存在")
    summary = _site_summary(db, site)
    water_history = list(
        db.scalars(
            select(WaterState)
            .where(WaterState.site_id == site_id)
            .order_by(WaterState.observed_at.desc())
            .limit(60)
        )
    )
    water_history.reverse()
    detail = SiteDetail(
        **summary.model_dump(),
        catchment_area_m2=site.catchment_area_m2,
        drainage_capacity_m3_min=site.drainage_capacity_m3_min,
        dem_version=site.dem_version,
        calibration_version=site.calibration_version,
        description=site.description,
        tags=site.tags,
        devices=[DeviceRead.model_validate(device) for device in site.devices],
        water_history=[WaterStateRead.model_validate(item) for item in water_history],
    )
    return detail.model_dump(by_alias=True, mode="json")


@router.get("/sites/{site_id}/water-states", tags=["sites"])
def site_water_states(
    site_id: str,
    limit: int = Query(default=60, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    if db.get(Site, site_id) is None:
        raise HTTPException(status_code=404, detail="监测点不存在")
    rows = list(
        db.scalars(
            select(WaterState)
            .where(WaterState.site_id == site_id)
            .order_by(WaterState.observed_at.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return [_dump(WaterStateRead, row) for row in rows]


@router.get("/sites/{site_id}/forecast", tags=["sites"])
def site_forecast(site_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    forecast = _latest_forecast(db, site_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="暂无有效预报")
    return _dump(ForecastRunRead, forecast)


@router.get("/events", tags=["events"])
def list_events(
    site_id: str | None = None,
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return _event_timeline(db, limit=limit, site_id=site_id)


@router.get("/alerts", tags=["alerts"])
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    site_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(Alert).order_by(Alert.updated_at.desc())
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    if site_id:
        stmt = stmt.where(Alert.site_id == site_id)
    return [_dump(AlertRead, row) for row in db.scalars(stmt)]


@router.get("/reviews", tags=["review"])
def list_reviews(
    site_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(ForecastRun)
        .options(selectinload(ForecastRun.points))
        .order_by(ForecastRun.created_at.desc())
        .limit(limit)
    )
    if site_id:
        stmt = stmt.where(ForecastRun.site_id == site_id)
    return [_dump(ForecastRunRead, row) for row in db.scalars(stmt)]


@router.get("/reviews/{forecast_run_id}", tags=["review"])
@router.get("/review/{forecast_run_id}", tags=["review"], include_in_schema=False)
def review_detail(forecast_run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    forecast = db.scalar(
        select(ForecastRun)
        .options(selectinload(ForecastRun.points), selectinload(ForecastRun.steps))
        .where(ForecastRun.id == forecast_run_id)
    )
    if forecast is None:
        raise HTTPException(status_code=404, detail="推理记录不存在")
    site = db.get(Site, forecast.site_id)
    assert site is not None
    alerts = list(db.scalars(select(Alert).where(Alert.forecast_run_id == forecast.id)))
    alert_ids = [alert.id for alert in alerts]
    actions = (
        list(db.scalars(select(ActionRecord).where(ActionRecord.alert_id.in_(alert_ids))))
        if alert_ids
        else []
    )
    audits = list(
        db.scalars(
            select(AuditLog)
            .where(
                or_(
                    AuditLog.trace_id == forecast.trace_id,
                    AuditLog.resource_id == forecast.id,
                    AuditLog.resource_id.in_([action.id for action in actions] or ["__none__"]),
                )
            )
            .order_by(AuditLog.occurred_at.asc())
        )
    )
    detail = ReviewDetail(
        forecast=ForecastRunRead.model_validate(forecast),
        site=_site_summary(db, site),
        inference_steps=[InferenceStepRead.model_validate(step) for step in forecast.steps],
        related_alerts=[AlertRead.model_validate(alert) for alert in alerts],
        related_actions=[ActionRead.model_validate(action) for action in actions],
        audit_trail=[AuditLogRead.model_validate(audit) for audit in audits],
        input_snapshot=forecast.input_snapshot,
        physics_checks=forecast.physics_checks,
    )
    return detail.model_dump(by_alias=True, mode="json")


@router.get("/devices", tags=["devices"])
def list_devices(
    site_id: str | None = None,
    device_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(Device).order_by(Device.site_id.asc(), Device.device_type.asc())
    if site_id:
        stmt = stmt.where(Device.site_id == site_id)
    if device_type:
        stmt = stmt.where(Device.device_type == device_type)
    if status_filter:
        stmt = stmt.where(Device.status == status_filter)
    return [_dump(DeviceRead, row) for row in db.scalars(stmt)]


@router.get("/devices/{device_id}", tags=["devices"])
def get_device(device_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return _dump(DeviceRead, device)


@router.get("/audit", tags=["audit"])
def list_audit_logs(
    site_id: str | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(limit)
    if site_id:
        stmt = stmt.where(AuditLog.site_id == site_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return [_dump(AuditLogRead, row) for row in db.scalars(stmt)]


@router.get("/audit/verify", tags=["audit"])
def verify_audit(db: Session = Depends(get_db)) -> dict[str, Any]:
    return verify_audit_chain(db)


@router.get("/actions", tags=["actions"])
def list_actions(
    status_filter: str | None = Query(default=None, alias="status"),
    site_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(ActionRecord).order_by(ActionRecord.requested_at.desc())
    if status_filter:
        stmt = stmt.where(ActionRecord.status == status_filter)
    if site_id:
        stmt = stmt.where(ActionRecord.site_id == site_id)
    return [_dump(ActionRead, row) for row in db.scalars(stmt)]


async def _decide_action(
    action_id: str,
    decision: ActionDecision,
    approved: bool,
    request: Request,
    db: Session,
) -> dict[str, Any]:
    action = db.get(ActionRecord, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="联动动作不存在")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail=f"动作当前状态为 {action.status}，不能重复决策")
    now = utcnow()
    action.status = "confirmed" if approved else "rejected"
    action.decided_at = now
    action.decided_by = decision.actor_id
    action.decision_reason = decision.reason
    append_audit(
        db,
        action="action.confirmed" if approved else "action.rejected",
        resource_type="action_record",
        resource_id=action.id,
        site_id=action.site_id,
        actor_type="user",
        actor_id=decision.actor_id,
        detail={
            "decision": action.status,
            "reason": decision.reason,
            "targetId": action.target_id,
            "idempotencyKey": action.idempotency_key,
        },
    )
    db.commit()
    payload = _dump(ActionRead, action)
    await request.app.state.broker.publish(f"action.{action.status}", payload)
    return payload


@router.post("/actions/{action_id}/confirm", tags=["actions"])
async def confirm_action(
    action_id: str,
    decision: ActionDecision,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await _decide_action(action_id, decision, True, request, db)


@router.post("/actions/{action_id}/reject", tags=["actions"])
async def reject_action(
    action_id: str,
    decision: ActionDecision,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await _decide_action(action_id, decision, False, request, db)


@router.get("/scenarios", tags=["scenarios"])
def scenario_catalog(request: Request) -> list[dict[str, Any]]:
    manager: ScenarioManager = request.app.state.scenario_manager
    return manager.catalog


@router.get("/scenarios/runs", tags=["scenarios"])
def scenario_runs(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(ScenarioRun).order_by(ScenarioRun.updated_at.desc()))
    return [_dump(ScenarioRunRead, row) for row in rows]


@router.post("/scenarios/{scenario_key}/start", tags=["scenarios"], status_code=status.HTTP_201_CREATED)
async def start_scenario(
    scenario_key: str,
    body: ScenarioStartRequest,
    request: Request,
) -> dict[str, Any]:
    manager: ScenarioManager = request.app.state.scenario_manager
    try:
        run = await manager.create_run(
            scenario_key,
            body.site_id,
            body.speed,
            auto_run=body.auto_run,
        )
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"场景或点位不存在：{exc.args[0]}") from exc
    return _dump(ScenarioRunRead, run)


async def _scenario_operation(request: Request, run_id: str, operation: str) -> dict[str, Any]:
    manager: ScenarioManager = request.app.state.scenario_manager
    try:
        if operation == "pause":
            result: Any = await manager.pause(run_id)
        elif operation == "resume":
            result = await manager.resume(run_id)
        elif operation == "reset":
            result = await manager.reset(run_id)
        else:
            return await manager.step(run_id)
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"场景运行不存在：{exc.args[0]}") from exc
    return _dump(ScenarioRunRead, result)


@router.post("/scenarios/runs/{run_id}/pause", tags=["scenarios"])
@router.post("/scenarios/{run_id}/pause", tags=["scenarios"], include_in_schema=False)
async def pause_scenario(run_id: str, request: Request) -> dict[str, Any]:
    return await _scenario_operation(request, run_id, "pause")


@router.post("/scenarios/runs/{run_id}/resume", tags=["scenarios"])
@router.post("/scenarios/{run_id}/resume", tags=["scenarios"], include_in_schema=False)
async def resume_scenario(run_id: str, request: Request) -> dict[str, Any]:
    return await _scenario_operation(request, run_id, "resume")


@router.post("/scenarios/runs/{run_id}/reset", tags=["scenarios"])
@router.post("/scenarios/{run_id}/reset", tags=["scenarios"], include_in_schema=False)
async def reset_scenario(run_id: str, request: Request) -> dict[str, Any]:
    return await _scenario_operation(request, run_id, "reset")


@router.post("/scenarios/runs/{run_id}/step", tags=["scenarios"])
@router.post("/scenarios/{run_id}/step", tags=["scenarios"], include_in_schema=False)
async def step_scenario(run_id: str, request: Request) -> dict[str, Any]:
    return await _scenario_operation(request, run_id, "step")


def _payload_value(payload: dict[str, Any], camel: str, snake: str, default: Any = 0) -> Any:
    if camel in payload:
        return payload[camel]
    return payload.get(snake, default)

def _resolve_unified_edge_device(
    db: Session,
    *,
    site_id: str,
    station_id: str,
    edge_node_id: str,
) -> Device:
    device = db.get(Device, edge_node_id)
    if device and device.site_id == site_id and device.station_id == station_id:
        return device
    device = db.scalar(
        select(Device)
        .where(
            Device.site_id == site_id,
            Device.station_id == station_id,
            Device.device_type == "gateway",
        )
        .limit(1)
    )
    if device is None:
        device = db.scalar(
            select(Device)
            .where(Device.site_id == site_id, Device.station_id == station_id)
            .order_by(Device.device_type.asc())
            .limit(1)
        )
    if device is None:
        raise HTTPException(status_code=404, detail="统一信封中的站点或边缘节点未注册")
    return device


def _normalize_unified_water_event(
    body: EdgeUnifiedEnvelope,
    db: Session,
) -> EdgeTelemetryEnvelope:
    if body.event_type != "water.state.v1":
        raise HTTPException(status_code=422, detail=f"事件 {body.event_type} 不是水状态事件")
    site_id = body.subject.site_id
    station_id = body.subject.station_id
    device = _resolve_unified_edge_device(
        db,
        site_id=site_id,
        station_id=station_id,
        edge_node_id=body.source.edge_node_id,
    )
    payload = body.payload
    maximum = float(payload.get("maxDepthCm", 0))
    rise_rate = float(payload.get("riseRateCmPerMin", 0))
    context = body.context
    quality_status = {
        "good": "accepted",
        "degraded": "weighted",
        "poor": "filled",
        "bad": "rejected",
    }.get(body.quality.status, body.quality.status)
    return EdgeTelemetryEnvelope(
        event_id=body.event_id,
        schema_version=1,
        event_type="water.state",
        tenant_id=body.source.tenant_id,
        site_id=site_id,
        station_id=station_id,
        device_id=device.id,
        event_time=body.occurred_at,
        sequence_no=body.sequence,
        trace_id=body.trace_id,
        refs={
            "demVersion": str(payload.get("demVersion") or context.get("demVersion") or ""),
            "calibrationVersion": str(context.get("cameraCalibrationVersion") or ""),
            "modelVersion": str(context.get("adapterVersion") or "edge-adapter-v1"),
            "configVersion": str(context.get("configVersion") or ""),
        },
        quality={
            "score": body.quality.confidence,
            "status": quality_status,
            "flags": body.quality.reasons,
        },
        payload={
            "avgDepthCm": float(payload.get("averageDepthCm", payload.get("avgDepthCm", 0))),
            "maxDepthCm": maximum,
            "areaM2": float(payload.get("areaM2", 0)),
            "volumeM3": float(payload.get("volumeM3", 0)),
            "depthSegmentsCm": payload.get(
                "depthSegmentsCm",
                [round(maximum * factor, 2) for factor in (0.34, 0.68, 1.0, 0.76, 0.41)],
            ),
            "slope1mCmMin": rise_rate,
            "slope5mCmMin": rise_rate,
            "slope10mCmMin": rise_rate,
            "drainageSaturation": "red" if rise_rate >= 0.5 else "yellow" if rise_rate > 0 else "green",
            "boundaryGeojson": {},
            "state": payload.get("state", "unknown"),
            "observationWindowSeconds": payload.get("observationWindowSeconds"),
        },
    )


async def _ingest_unified_auxiliary_event(
    body: EdgeUnifiedEnvelope,
    request: Request,
    db: Session,
) -> dict[str, Any]:
    supported = {"edge.heartbeat.v1", "water.boundary.v1", "road.dem.metadata.v1", "edge.command.ack.v1"}
    if body.event_type not in supported:
        raise HTTPException(status_code=422, detail=f"暂不支持统一信封事件：{body.event_type}")
    existing = db.scalar(
        select(AuditLog).where(
            AuditLog.resource_id == body.event_id,
            AuditLog.action == "edge.unified.accepted",
        )
    )
    if existing:
        return {"accepted": True, "duplicate": True, "eventId": body.event_id, "eventType": body.event_type}
    site = db.get(Site, body.subject.site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="统一信封中的监测点未注册")
    device = _resolve_unified_edge_device(
        db,
        site_id=body.subject.site_id,
        station_id=body.subject.station_id,
        edge_node_id=body.source.edge_node_id,
    )
    record_id: str | int = device.id
    if body.event_type == "edge.heartbeat.v1":
        device.status = str(body.payload.get("status", "online"))
        device.last_seen_at = body.occurred_at
        device.telemetry = {**device.telemetry, "edgeRuntime": body.payload, "edgeContext": body.context}
    elif body.event_type == "water.boundary.v1":
        state = _latest_water(db, site.id)
        polygon = body.payload.get("polygon", [])
        if state and polygon:
            coordinates = [[float(point["x"]), float(point["y"])] for point in polygon]
            if coordinates and coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            state.boundary_geojson = {"type": "Polygon", "coordinates": [coordinates]}
            record_id = state.id
    elif body.event_type == "road.dem.metadata.v1":
        site.dem_version = str(body.payload.get("demVersion", site.dem_version))
        device.telemetry = {**device.telemetry, "latestDem": body.payload}
        record_id = site.id
    else:
        action_id = str(body.payload.get("actionId") or body.payload.get("commandId") or "")
        action_record = db.get(ActionRecord, action_id) if action_id else None
        if action_record:
            ack_status = str(body.payload.get("status", "acked"))
            action_record.status = "failed" if ack_status == "failed" else "acked"
            action_record.acknowledged_at = body.occurred_at
            action_record.edge_response = body.payload
            record_id = action_record.id
    append_audit(
        db,
        action="edge.unified.accepted",
        resource_type=body.event_type,
        resource_id=body.event_id,
        site_id=site.id,
        actor_type="device",
        actor_id=body.source.edge_node_id,
        trace_id=body.trace_id,
        detail={"sequence": body.sequence, "recordId": record_id, "schemaVersion": body.schema_version},
        occurred_at=body.occurred_at,
    )
    db.commit()
    event_payload = {
        "accepted": True,
        "duplicate": False,

        "eventId": body.event_id,
        "eventType": body.event_type,
        "recordId": record_id,
        "siteId": site.id,
    }
    await request.app.state.broker.publish("edge.telemetry.accepted", event_payload)
    return event_payload



@edge_router.post("/heartbeat")
async def edge_heartbeat(
    body: EdgeHeartbeat,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    device = db.get(Device, body.device_id)
    if device is None or device.site_id != body.site_id or device.station_id != body.station_id:
        raise HTTPException(status_code=404, detail="设备身份与站点绑定不匹配")
    device.last_seen_at = body.event_time
    device.status = body.status
    device.telemetry = {**device.telemetry, **body.telemetry}
    if body.firmware_version:
        device.firmware_version = body.firmware_version
    db.commit()
    payload = {"accepted": True, "serverTime": utcnow(), "desiredConfig": device.desired_config}
    await request.app.state.broker.publish(
        "device.heartbeat", {"deviceId": device.id, "siteId": device.site_id, "status": device.status}
    )
    return payload


@edge_router.post("/telemetry", status_code=status.HTTP_202_ACCEPTED)
async def ingest_edge_telemetry(
    body: EdgeUnifiedEnvelope | EdgeTelemetryEnvelope,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    wire_event_type = body.event_type
    if isinstance(body, EdgeUnifiedEnvelope):
        if body.event_type != "water.state.v1":
            return await _ingest_unified_auxiliary_event(body, request, db)
        body = _normalize_unified_water_event(body, db)

    device = db.get(Device, body.device_id)
    if device is None or device.site_id != body.site_id or device.station_id != body.station_id:
        raise HTTPException(status_code=404, detail="设备身份与站点绑定不匹配")
    site = db.get(Site, body.site_id)
    assert site is not None
    if body.event_type == "water.state":
        duplicate = db.scalar(select(WaterState).where(WaterState.event_id == body.event_id))
        if duplicate:
            return {"accepted": True, "duplicate": True, "recordId": duplicate.id}
        confidence_raw = float(body.quality.get("score", 100))
        confidence = confidence_raw / 100 if confidence_raw > 1 else confidence_raw
        payload = body.payload
        water = WaterState(
            site_id=body.site_id,
            observed_at=body.event_time,
            sequence_no=body.sequence_no,
            avg_depth_cm=float(_payload_value(payload, "avgDepthCm", "avg_depth_cm")),
            max_depth_cm=float(_payload_value(payload, "maxDepthCm", "max_depth_cm")),
            area_m2=float(_payload_value(payload, "areaM2", "area_m2")),
            volume_m3=float(_payload_value(payload, "volumeM3", "volume_m3")),
            depth_segments_cm=list(_payload_value(payload, "depthSegmentsCm", "depth_segments_cm", [])),
            slope_1m_cm_min=float(_payload_value(payload, "slope1mCmMin", "slope_1m_cm_min")),
            slope_5m_cm_min=float(_payload_value(payload, "slope5mCmMin", "slope_5m_cm_min")),
            slope_10m_cm_min=float(_payload_value(payload, "slope10mCmMin", "slope_10m_cm_min")),
            drainage_saturation=str(_payload_value(payload, "drainageSaturation", "drainage_saturation", "green")),
            confidence=confidence,
            quality_status=str(body.quality.get("status", "accepted")),
            quality_flags=list(body.quality.get("flags", [])),
            dem_version=body.refs.get("demVersion", site.dem_version),
            calibration_version=body.refs.get("calibrationVersion", site.calibration_version),
            model_version=body.refs.get("modelVersion", "reflection-v0.4.2"),
            boundary_geojson=dict(_payload_value(payload, "boundaryGeojson", "boundary_geojson", {})),
            source="ubuntu-edge",
            event_id=body.event_id,
        )
        db.add(water)
        db.flush()
        weather = _latest_weather(db, site.id)
        forecast_id = None
        if weather:
            forecast = create_forecast_run(
                db,
                site=site,
                water_state=water,
                weather=weather,
                trigger_type="edge_event",
                created_at=body.event_time,
            )
            forecast_id = forecast.id
        record_id = water.id
    else:
        payload = body.payload
        weather = WeatherSnapshot(
            site_id=body.site_id,
            observed_at=body.event_time,
            issued_at=body.event_time,
            condition=str(_payload_value(payload, "condition", "condition", "rain")),
            rainfall_mm_h=float(_payload_value(payload, "rainfallMmH", "rainfall_mm_h")),
            forecast_15m_mm=float(_payload_value(payload, "forecast15mMm", "forecast_15m_mm")),
            forecast_30m_mm=float(_payload_value(payload, "forecast30mMm", "forecast_30m_mm")),
            forecast_60m_mm=float(_payload_value(payload, "forecast60mMm", "forecast_60m_mm")),
            temperature_c=float(_payload_value(payload, "temperatureC", "temperature_c", 24)),
            humidity_pct=float(_payload_value(payload, "humidityPct", "humidity_pct", 80)),
            wind_m_s=float(_payload_value(payload, "windMS", "wind_m_s", 0)),
            source="ubuntu-edge",
            confidence=float(body.quality.get("score", 90)) / 100,
            raw_payload={"eventId": body.event_id, **payload},
        )
        db.add(weather)
        db.flush()
        record_id = weather.id
        forecast_id = None
    device.last_seen_at = body.event_time
    device.status = "online"
    append_audit(
        db,
        action="edge.telemetry.accepted",
        resource_type=body.event_type,
        resource_id=body.event_id,
        site_id=body.site_id,
        actor_type="device",
        actor_id=body.device_id,
        trace_id=body.trace_id,
        detail={"sequenceNo": body.sequence_no, "recordId": record_id, "schemaVersion": body.schema_version},
        occurred_at=body.event_time,
    )
    db.commit()
    event_payload = {
        "eventId": body.event_id,
        "eventType": wire_event_type,
        "siteId": body.site_id,
        "recordId": record_id,
        "forecastRunId": forecast_id,
    }
    await request.app.state.broker.publish("edge.telemetry.accepted", event_payload)
    return {"accepted": True, "duplicate": False, **event_payload}


@edge_router.get("/stations/{station_id}/commands")
def edge_commands(
    station_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    target_ids = list(db.scalars(select(Device.id).where(Device.station_id == station_id)))
    if not target_ids:
        raise HTTPException(status_code=404, detail="边缘站不存在")
    actions = list(
        db.scalars(
            select(ActionRecord)
            .where(
                ActionRecord.target_id.in_(target_ids),
                ActionRecord.status.in_(["confirmed", "dispatched"]),
            )
            .order_by(ActionRecord.requested_at.asc())
        )
    )
    now = utcnow()
    for action in actions:
        if action.status == "confirmed":
            action.status = "dispatched"
            action.dispatched_at = now
            append_audit(
                db,
                action="command.dispatched",
                resource_type="action_record",
                resource_id=action.id,
                site_id=action.site_id,
                actor_type="service",
                actor_id="edge-command-api",
                detail={"stationId": station_id, "targetId": action.target_id},
            )
    db.commit()
    return [_dump(ActionRead, action) for action in actions]


@edge_router.post("/commands/{action_id}/ack")
async def acknowledge_edge_command(
    action_id: str,
    body: EdgeCommandAck,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    action = db.get(ActionRecord, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="指令不存在")
    device = db.get(Device, action.target_id)
    if device is None or device.station_id != body.station_id:
        raise HTTPException(status_code=403, detail="边缘站无权回执该指令")
    if action.status not in {"dispatched", "acked", "confirmed"}:
        raise HTTPException(status_code=409, detail=f"指令状态 {action.status} 不接受设备回执")
    action.status = body.status
    action.acknowledged_at = body.acknowledged_at
    action.edge_response = {"deviceState": body.device_state, "message": body.message}
    append_audit(
        db,
        action=f"command.{body.status}",
        resource_type="action_record",
        resource_id=action.id,
        site_id=action.site_id,
        actor_type="device",
        actor_id=body.station_id,
        detail=action.edge_response,
        occurred_at=body.acknowledged_at,
    )
    db.commit()
    payload = _dump(ActionRead, action)
    await request.app.state.broker.publish(f"command.{body.status}", payload)
    return payload


@router.get("/events/stream", tags=["realtime"])
async def stream_events(request: Request) -> StreamingResponse:
    broker = request.app.state.broker
    keepalive = request.app.state.settings.event_stream_keepalive_seconds

    async def generator() -> AsyncIterator[str]:
        queue = await broker.add_subscriber()
        try:
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=keepalive)
                    yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive {datetime.now(timezone.utc).isoformat()}\n\n"
        finally:
            await broker.remove_subscriber(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@public_router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    with websocket.app.state.database.session_factory() as db:
        try:
            resolve_session(websocket, db, required=True)
        except HTTPException:
            await websocket.close(code=4401)
            return
    await websocket.accept()
    broker = websocket.app.state.broker
    queue = await broker.add_subscriber()
    try:
        await websocket.send_json({"type": "connected", "time": utcnow().isoformat(), "payload": {}})
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await broker.remove_subscriber(queue)
