from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .api import dashboard
from .audit import append_audit
from .auth import get_optional_session_user, require_session_user
from .database import get_db
from .models import (
    ActionRecord,
    Alert,
    AuditLog,
    ForecastRun,
    Site,
    WaterState,
    utcnow,
)
from .schemas import APIModel


router = APIRouter(tags=["ui-compat"], dependencies=[Depends(require_session_user)])
UI_EVENT_ID = "YJ-20260710-0148"
PRIMARY_SITE_ID = "site-binh-rd-tunnel"
ALLOWED_CHANNELS = {"gate", "led", "app", "patrol"}


class EventPublishRequest(APIModel):
    operator: str = Field(default="王海峰", min_length=2, max_length=80)
    channels: list[str] = Field(min_length=1, max_length=8)
    action: str = Field(default="确认预警并发布", min_length=2, max_length=240)


class ManualReviewRequest(APIModel):
    operator: str = Field(default="王海峰", min_length=2, max_length=80)
    reason: str = Field(min_length=2, max_length=500)


@dataclass(frozen=True)
class EventContext:
    event_id: str
    site: Site
    alert: Alert | None
    forecast: ForecastRun
    action: ActionRecord | None


def _request_operator(request: Request, db: Session, fallback: str) -> str:
    user = get_optional_session_user(request, db)
    return user.display_name if user else fallback


def _resolve_ui_event(db: Session, event_id: str) -> EventContext:
    site: Site | None = None
    alert: Alert | None = None
    forecast: ForecastRun | None = None
    action: ActionRecord | None = None

    if event_id == UI_EVENT_ID:
        site = db.get(Site, PRIMARY_SITE_ID)
    else:
        alert = db.get(Alert, event_id)
        if alert:
            site = db.get(Site, alert.site_id)
        if site is None:
            forecast = db.get(ForecastRun, event_id)
            if forecast:
                site = db.get(Site, forecast.site_id)
        if site is None:
            action = db.get(ActionRecord, event_id)
            if action:
                site = db.get(Site, action.site_id)

    if site is None:
        raise HTTPException(status_code=404, detail="演示事件不存在")

    if alert is None:
        alert = db.scalar(
            select(Alert)
            .where(Alert.site_id == site.id)
            .order_by(Alert.updated_at.desc(), Alert.created_at.desc())
            .limit(1)
        )
    if forecast is None:
        if alert and alert.forecast_run_id:
            forecast = db.get(ForecastRun, alert.forecast_run_id)
        if forecast is None:
            forecast = db.scalar(
                select(ForecastRun)
                .where(ForecastRun.site_id == site.id, ForecastRun.is_current.is_(True))
                .order_by(ForecastRun.created_at.desc())
                .limit(1)
            )
    if forecast is None:
        raise HTTPException(status_code=409, detail="事件尚无可发布的预测结果")
    if action is None:
        if alert:
            action = db.scalar(
                select(ActionRecord)
                .where(ActionRecord.alert_id == alert.id)
                .order_by(ActionRecord.requested_at.desc())
                .limit(1)
            )
        if action is None:
            action = db.scalar(
                select(ActionRecord)
                .where(ActionRecord.site_id == site.id)
                .order_by(ActionRecord.requested_at.desc())
                .limit(1)
            )
    return EventContext(event_id=event_id, site=site, alert=alert, forecast=forecast, action=action)


def _ordered_channels(channels: list[str]) -> list[str]:
    unique = list(dict.fromkeys(channel.strip().lower() for channel in channels if channel.strip()))
    invalid = [channel for channel in unique if channel not in ALLOWED_CHANNELS]
    if invalid:
        raise HTTPException(status_code=422, detail=f"不支持的发布渠道：{', '.join(invalid)}")
    if not unique:
        raise HTTPException(status_code=422, detail="至少选择一个发布渠道")
    return unique


@router.post("/events/{event_id}/publish")
async def publish_ui_event(
    event_id: str,
    body: EventPublishRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    context = _resolve_ui_event(db, event_id)
    operator = _request_operator(request, db, body.operator)
    if context.action is None:
        raise HTTPException(status_code=409, detail="事件没有可确认的联动动作")
    action = context.action
    existing_publication = action.edge_response.get("uiPublication")
    if existing_publication and action.status in {"confirmed", "dispatched", "acked", "verified"}:
        return {"ok": True, "eventId": event_id, "idempotent": True, **existing_publication}
    if action.status == "rejected":
        raise HTTPException(status_code=409, detail="联动动作已退回人工复核，不能直接发布")
    if action.status not in {"pending", "confirmed"}:
        raise HTTPException(status_code=409, detail=f"联动动作状态 {action.status} 不允许发布")

    channels = _ordered_channels(body.channels)
    now = utcnow()
    receipt_id = f"PUB-{now:%Y%m%d%H%M%S}-{action.id[-6:].upper()}"
    receipts = [
        {
            "channel": channel,
            "status": "queued" if channel == "gate" else "accepted",
            "receiptId": f"{receipt_id}-{channel.upper()}",
        }
        for channel in channels
    ]
    publication = {
        "publishedAt": now.isoformat(),
        "receiptId": receipt_id,
        "channels": channels,
        "receipts": receipts,
        "actionId": action.id,
        "actionStatus": "confirmed",
        "alertId": context.alert.id if context.alert else None,
        "forecastRunId": context.forecast.id,
    }
    action.status = "confirmed"
    action.decided_at = now
    action.decided_by = operator
    action.decision_reason = body.action
    action.command_payload = {
        **action.command_payload,
        "publication": {"eventId": event_id, "channels": channels, "operator": operator},
    }
    action.edge_response = {**action.edge_response, "uiPublication": publication}
    if context.alert:
        context.alert.status = "acknowledged"
        context.alert.acknowledged_at = now
        context.alert.acknowledged_by = operator
    append_audit(
        db,
        action="event.warning.published",
        resource_type="ui_event",
        resource_id=event_id,
        site_id=context.site.id,
        actor_type="user",
        actor_id=operator,
        trace_id=context.forecast.trace_id,
        detail={
            "actionId": action.id,
            "alertId": context.alert.id if context.alert else None,
            "forecastRunId": context.forecast.id,
            "channels": channels,
            "receipts": receipts,
            "decision": body.action,
        },
        occurred_at=now,
    )
    db.commit()
    response = {"ok": True, "eventId": event_id, "idempotent": False, **publication}
    await request.app.state.broker.publish("event.warning.published", response)
    return response


@router.post("/events/{event_id}/manual-review")
async def queue_ui_manual_review(
    event_id: str,
    body: ManualReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    context = _resolve_ui_event(db, event_id)
    operator = _request_operator(request, db, body.operator)
    if context.action is None:
        raise HTTPException(status_code=409, detail="事件没有可退回的联动动作")
    action = context.action
    existing_review = action.edge_response.get("manualReview")
    if existing_review and action.status == "rejected":
        return {"ok": True, "eventId": event_id, "idempotent": True, **existing_review}
    if action.status not in {"pending", "rejected"}:
        raise HTTPException(status_code=409, detail=f"联动动作状态 {action.status} 不能退回复核")

    now = utcnow()
    review = {
        "queuedAt": now.isoformat(),
        "queue": "防汛人工复核队列",
        "reason": body.reason,
        "operator": operator,
        "actionId": action.id,
        "actionStatus": "rejected",
        "alertId": context.alert.id if context.alert else None,
        "forecastRunId": context.forecast.id,
    }
    action.status = "rejected"
    action.decided_at = now
    action.decided_by = operator
    action.decision_reason = body.reason
    action.edge_response = {**action.edge_response, "manualReview": review}
    if context.alert:
        context.alert.status = "manual_review"
        context.alert.updated_at = now
    append_audit(
        db,
        action="event.manual_review.queued",
        resource_type="ui_event",
        resource_id=event_id,
        site_id=context.site.id,
        actor_type="user",
        actor_id=operator,
        trace_id=context.forecast.trace_id,
        detail={
            "actionId": action.id,
            "alertId": context.alert.id if context.alert else None,
            "forecastRunId": context.forecast.id,
            "queue": review["queue"],
            "reason": body.reason,
        },
        occurred_at=now,
    )
    db.commit()
    response = {"ok": True, "eventId": event_id, "idempotent": False, **review}
    await request.app.state.broker.publish("event.manual_review.queued", response)
    return response


def _dem_age_days(dem_version: str, captured_at: datetime) -> int | None:
    match = re.search(r"(20\d{6})", dem_version)
    if not match:
        return None
    try:
        scanned = datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None
    observed = captured_at.date()
    return max(0, (observed - scanned).days)


@router.get("/events/{event_id}/evidence")
def get_ui_event_evidence(event_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    context = _resolve_ui_event(db, event_id)
    water = db.scalar(
        select(WaterState)
        .where(WaterState.site_id == context.site.id)
        .order_by(WaterState.observed_at.desc(), WaterState.id.desc())
        .limit(1)
    )
    if water is None:
        raise HTTPException(status_code=409, detail="事件尚无原始积水观测")
    audit = db.scalar(
        select(AuditLog)
        .where(
            or_(
                AuditLog.trace_id == context.forecast.trace_id,
                AuditLog.resource_id == context.forecast.id,
                AuditLog.site_id == context.site.id,
            )
        )
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .limit(1)
    )
    image_quality = round(max(0, min(100, water.confidence * 100)))
    effective_pixels = round(max(0, min(100, image_quality * 0.87)))
    boundary_iou = round(max(0, min(1, water.confidence - 0.10)), 2)
    captured_at = water.observed_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    checksum = audit.entry_hash if audit else context.forecast.trace_id
    return {
        "ok": True,
        "eventId": event_id,
        "capturedAt": captured_at.isoformat(),
        "frameId": f"FRAME-{context.site.id.upper()}-{water.id:06d}",
        "imageQuality": image_quality,
        "effectivePixels": effective_pixels,
        "demVersion": water.dem_version,
        "demAgeDays": _dem_age_days(water.dem_version, captured_at),
        "boundaryIou": boundary_iou,
        "maximumDepth": round(water.max_depth_cm, 1),
        "floodedArea": round(water.area_m2, 1),
        "floodedVolume": round(water.volume_m3, 2),
        "confidence": round(context.forecast.confidence),
        "checksum": checksum,
        "alertId": context.alert.id if context.alert else None,
        "forecastRunId": context.forecast.id,
        "actionId": context.action.id if context.action else None,
        "traceId": context.forecast.trace_id,
        "rulesVersion": context.forecast.rules_version,
        "modelVersion": context.forecast.model_version,
    }


@router.get("/snapshot")
def get_ui_snapshot(db: Session = Depends(get_db)) -> dict[str, Any]:
    summary = dashboard(db)
    return {
        "ok": True,
        "updatedAt": summary["generatedAt"],
        "source": "server-persisted-demo",
        "overview": summary["overview"],
        "primarySite": summary["primarySite"],
        "sites": summary["sites"],
        "forecastCurve": summary["forecastCurve"],
        "events": summary["events"],
    }
