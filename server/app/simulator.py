from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .audit import append_audit
from .database import Database
from .inference import create_forecast_run, risk_level_for_depth
from .models import (
    ActionRecord,
    Alert,
    Device,
    ForecastPoint,
    ForecastRun,
    InferenceStep,
    ScenarioRun,
    Site,
    WaterState,
    WeatherSnapshot,
    utcnow,
)
from .realtime import RealtimeBroker


SCENARIO_CATALOG: dict[str, dict[str, Any]] = {
    "rapid-inundation": {
        "name": "短时暴雨 · 隧道快速积水",
        "description": "模拟降雨突增、排水饱和、达险预报和道闸联动建议的完整闭环。",
        "recommendedSiteId": "site-binh-rd-tunnel",
        "durationMinutes": 20,
        "rainfall": [18, 22, 28, 34, 42, 48, 52, 54, 51, 47, 42, 36, 30, 24, 18, 13, 9, 6, 3, 0, 0],
        "depth": [7.2, 8.1, 9.4, 11.0, 13.1, 15.8, 18.9, 22.4, 26.1, 29.8, 33.2, 36.3, 39.1, 41.3, 42.7, 43.2, 42.8, 41.8, 40.1, 37.9, 35.5],
        "quality": [0.96, 0.96, 0.95, 0.95, 0.94, 0.94, 0.93, 0.92, 0.92, 0.91, 0.91, 0.92, 0.92, 0.93, 0.94, 0.95, 0.95, 0.96, 0.96, 0.97, 0.97],
    },
    "camera-degradation": {
        "name": "极端雨幕 · 视觉质量降级",
        "description": "模拟有效像素率下降、L1 标记低置信并使用时序补位的审计过程。",
        "recommendedSiteId": "site-binh-rd-tunnel",
        "durationMinutes": 12,
        "rainfall": [28, 34, 42, 55, 62, 68, 71, 66, 58, 45, 32, 21, 12],
        "depth": [9.0, 10.2, 11.8, 13.9, 16.3, 19.0, 21.8, 24.3, 26.5, 28.2, 29.5, 30.1, 30.0],
        "quality": [0.92, 0.88, 0.80, 0.67, 0.56, 0.48, 0.44, 0.52, 0.61, 0.72, 0.83, 0.90, 0.94],
    },
    "drainage-recovery": {
        "name": "降雨停止 · 排水恢复",
        "description": "模拟降雨停止后水位回落、风险解除与解除封控建议。",
        "recommendedSiteId": "site-binh-rd-tunnel",
        "durationMinutes": 15,
        "rainfall": [24, 20, 15, 10, 5, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "depth": [38.0, 38.7, 39.0, 38.8, 38.2, 37.3, 36.1, 34.7, 33.0, 31.1, 29.0, 26.8, 24.5, 22.1, 19.7, 17.3],
        "quality": [0.94] * 16,
    },
}


class ScenarioNotFoundError(KeyError):
    pass


class ScenarioManager:
    def __init__(
        self,
        database: Database,
        broker: RealtimeBroker,
        tick_seconds: float = 2.0,
    ) -> None:
        self.database = database
        self.broker = broker
        self.tick_seconds = tick_seconds
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def catalog(self) -> list[dict[str, Any]]:
        return [
            {"key": key, **{k: v for k, v in value.items() if k not in {"rainfall", "depth", "quality"}}}
            for key, value in SCENARIO_CATALOG.items()
        ]

    async def create_run(
        self,
        scenario_key: str,
        site_id: str,
        speed: float,
        *,
        auto_run: bool,
    ) -> ScenarioRun:
        if scenario_key not in SCENARIO_CATALOG:
            raise ScenarioNotFoundError(scenario_key)
        with self.database.session_factory() as db:
            site = db.get(Site, site_id)
            if site is None:
                raise ScenarioNotFoundError(site_id)
            base_time = utcnow().replace(microsecond=0)
            run = ScenarioRun(
                id=f"scenario-{uuid4().hex[:16]}",
                scenario_key=scenario_key,
                site_id=site_id,
                status="running" if auto_run else "paused",
                tick_index=0,
                simulated_minutes=0,
                speed=speed,
                seed=5101,
                started_at=base_time,
                paused_at=None if auto_run else base_time,
                config={
                    "baseTime": base_time.isoformat(),
                    "source": "deterministic-simulator",
                    "catalogVersion": "2026.07.1",
                },
            )
            db.add(run)
            db.commit()
            run_id = run.id

        await self._write_tick(run_id, tick_index=0)
        if auto_run:
            self._schedule(run_id)
        with self.database.session_factory() as db:
            return db.get(ScenarioRun, run_id)  # type: ignore[return-value]

    def _schedule(self, run_id: str) -> None:
        existing = self._tasks.get(run_id)
        if existing and not existing.done():
            return
        self._tasks[run_id] = asyncio.create_task(self._run_loop(run_id), name=f"scenario:{run_id}")

    async def _run_loop(self, run_id: str) -> None:
        try:
            while True:
                with self.database.session_factory() as db:
                    run = db.get(ScenarioRun, run_id)
                    if run is None or run.status != "running":
                        break
                    delay = max(0.05, self.tick_seconds / max(run.speed, 0.25))
                await asyncio.sleep(delay)
                result = await self.step(run_id)
                if result["status"] == "completed":
                    break
        except asyncio.CancelledError:
            raise
        finally:
            self._tasks.pop(run_id, None)

    async def step(self, run_id: str) -> dict[str, Any]:
        lock = self._locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            with self.database.session_factory() as db:
                run = db.get(ScenarioRun, run_id)
                if run is None:
                    raise ScenarioNotFoundError(run_id)
                catalog = SCENARIO_CATALOG[run.scenario_key]
                next_tick = run.tick_index + 1
                if next_tick >= len(catalog["depth"]):
                    run.status = "completed"
                    run.completed_at = utcnow()
                    db.commit()
                    payload = {"runId": run_id, "status": "completed", "tickIndex": run.tick_index}
                    await self.broker.publish("scenario.completed", payload)
                    return payload
            # The per-run lock is already held; reacquiring it would deadlock.
            return self._write_tick_sync(run_id, next_tick)

    async def pause(self, run_id: str) -> ScenarioRun:
        with self.database.session_factory() as db:
            run = db.get(ScenarioRun, run_id)
            if run is None:
                raise ScenarioNotFoundError(run_id)
            if run.status not in {"completed", "reset"}:
                run.status = "paused"
                run.paused_at = utcnow()
                append_audit(
                    db,
                    action="scenario.paused",
                    resource_type="scenario_run",
                    resource_id=run.id,
                    site_id=run.site_id,
                    detail={"tickIndex": run.tick_index},
                    actor_type="operator",
                    actor_id="demo-operator",
                )
            db.commit()
            result = run
        task = self._tasks.get(run_id)
        if task and task is not asyncio.current_task():
            task.cancel()
        await self.broker.publish("scenario.paused", {"runId": run_id, "tickIndex": result.tick_index})
        return result

    async def resume(self, run_id: str) -> ScenarioRun:
        with self.database.session_factory() as db:
            run = db.get(ScenarioRun, run_id)
            if run is None:
                raise ScenarioNotFoundError(run_id)
            if run.status == "completed":
                return run
            run.status = "running"
            run.paused_at = None
            db.commit()
            result = run
        self._schedule(run_id)
        await self.broker.publish("scenario.resumed", {"runId": run_id, "tickIndex": result.tick_index})
        return result

    async def reset(self, run_id: str) -> ScenarioRun:
        task = self._tasks.get(run_id)
        if task and task is not asyncio.current_task():
            task.cancel()
        lock = self._locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            with self.database.session_factory() as db:
                run = db.get(ScenarioRun, run_id)
                if run is None:
                    raise ScenarioNotFoundError(run_id)
                self._delete_generated_data(db, run_id)
                run.status = "reset"
                run.tick_index = 0
                run.simulated_minutes = 0
                run.reset_at = utcnow()
                run.completed_at = None
                run.paused_at = None
                db.commit()
            await self._write_tick(run_id, tick_index=0, lock_already_held=True)
            with self.database.session_factory() as db:
                run = db.get(ScenarioRun, run_id)
                assert run is not None
                run.status = "reset"
                db.commit()
                result = run
        await self.broker.publish("scenario.reset", {"runId": run_id, "tickIndex": 0})
        return result

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def _delete_generated_data(self, db: Session, run_id: str) -> None:
        forecast_ids = list(
            db.scalars(select(ForecastRun.id).where(ForecastRun.scenario_run_id == run_id))
        )
        alert_ids = list(db.scalars(select(Alert.id).where(Alert.scenario_run_id == run_id)))
        if alert_ids:
            db.execute(delete(ActionRecord).where(ActionRecord.alert_id.in_(alert_ids)))
        db.execute(delete(ActionRecord).where(ActionRecord.scenario_run_id == run_id))
        db.execute(delete(Alert).where(Alert.scenario_run_id == run_id))
        if forecast_ids:
            db.execute(delete(InferenceStep).where(InferenceStep.forecast_run_id.in_(forecast_ids)))
            db.execute(delete(ForecastPoint).where(ForecastPoint.forecast_run_id.in_(forecast_ids)))
            db.execute(delete(ForecastRun).where(ForecastRun.id.in_(forecast_ids)))
        db.execute(delete(WaterState).where(WaterState.scenario_run_id == run_id))
        db.execute(delete(WeatherSnapshot).where(WeatherSnapshot.scenario_run_id == run_id))
        db.flush()

    async def _write_tick(
        self,
        run_id: str,
        tick_index: int,
        *,
        lock_already_held: bool = False,
    ) -> dict[str, Any]:
        if not lock_already_held:
            lock = self._locks.setdefault(run_id, asyncio.Lock())
            async with lock:
                return self._write_tick_sync(run_id, tick_index)
        return self._write_tick_sync(run_id, tick_index)

    def _write_tick_sync(self, run_id: str, tick_index: int) -> dict[str, Any]:
        with self.database.session_factory() as db:
            run = db.get(ScenarioRun, run_id)
            if run is None:
                raise ScenarioNotFoundError(run_id)
            site = db.get(Site, run.site_id)
            if site is None:
                raise ScenarioNotFoundError(run.site_id)
            catalog = SCENARIO_CATALOG[run.scenario_key]
            if tick_index >= len(catalog["depth"]):
                tick_index = len(catalog["depth"]) - 1

            base_time = datetime.fromisoformat(run.config["baseTime"])
            if base_time.tzinfo is None:
                base_time = base_time.replace(tzinfo=timezone.utc)
            event_time = base_time + timedelta(minutes=tick_index)
            depth = float(catalog["depth"][tick_index])
            previous_depth = float(catalog["depth"][max(0, tick_index - 1)])
            prior_5_depth = float(catalog["depth"][max(0, tick_index - 5)])
            prior_10_depth = float(catalog["depth"][max(0, tick_index - 10)])
            slope_1 = depth - previous_depth if tick_index else 0.0
            slope_5 = (depth - prior_5_depth) / max(1, min(5, tick_index)) if tick_index else 0.0
            slope_10 = (depth - prior_10_depth) / max(1, min(10, tick_index)) if tick_index else 0.0
            rainfall = float(catalog["rainfall"][tick_index])
            quality = float(catalog["quality"][tick_index])
            quality_flags: list[str] = []
            quality_status = "accepted"
            if quality < 0.60:
                quality_flags = ["LOW_EFFECTIVE_PIXELS", "TEMPORAL_FILL_USED"]
                quality_status = "filled"
            elif quality < 0.80:
                quality_flags = ["RAIN_CURTAIN"]
                quality_status = "weighted"

            area = min(site.coverage_area_m2 * 0.82, max(18.0, depth * 13.4))
            average_depth = depth * 0.61
            water = WaterState(
                site_id=site.id,
                scenario_run_id=run.id,
                observed_at=event_time,
                sequence_no=run.seed * 1000 + tick_index,
                avg_depth_cm=round(average_depth, 2),
                max_depth_cm=round(depth, 2),
                area_m2=round(area, 2),
                volume_m3=round(area * average_depth / 100, 2),
                depth_segments_cm=[round(depth * factor, 2) for factor in (0.31, 0.67, 1.0, 0.75, 0.38)],
                slope_1m_cm_min=round(slope_1, 3),
                slope_5m_cm_min=round(slope_5, 3),
                slope_10m_cm_min=round(slope_10, 3),
                drainage_saturation="red" if slope_5 > 0.55 else "yellow" if slope_5 > 0.15 else "green",
                confidence=quality,
                quality_status=quality_status,
                quality_flags=quality_flags,
                dem_version=site.dem_version,
                calibration_version=site.calibration_version,
                model_version="reflection-v0.4.2",
                boundary_geojson={
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [8 + depth / 5, 0], [10, 6], [2, 8], [0, 0]]],
                },
                source="deterministic-simulator",
                event_id=f"{run.id}:water:{tick_index}",
            )
            weather = WeatherSnapshot(
                site_id=site.id,
                scenario_run_id=run.id,
                observed_at=event_time,
                issued_at=event_time,
                condition="extreme_rain" if rainfall >= 50 else "heavy_rain" if rainfall >= 25 else "moderate_rain",
                rainfall_mm_h=rainfall,
                forecast_15m_mm=round(sum(catalog["rainfall"][tick_index : tick_index + 4]) / 4 * 0.25, 2),
                forecast_30m_mm=round(sum(catalog["rainfall"][tick_index : tick_index + 6]) / 6 * 0.5, 2),
                forecast_60m_mm=round(rainfall * 0.72, 2),
                temperature_c=23.4,
                humidity_pct=95.0,
                wind_m_s=4.1,
                source="deterministic-weather-simulator",
                confidence=max(0.72, quality),
                raw_payload={"scenarioRunId": run.id, "tickIndex": tick_index},
            )
            db.add_all([water, weather])
            db.flush()
            forecast = create_forecast_run(
                db,
                site=site,
                water_state=water,
                weather=weather,
                trigger_type="scenario_tick",
                scenario_run_id=run.id,
                created_at=event_time,
            )

            site.risk_level = forecast.risk_level
            site.current_mode = "rain" if rainfall > 0 else "drainage"
            alert = self._upsert_alert_and_action(db, run, site, forecast, event_time)
            run.tick_index = tick_index
            run.simulated_minutes = tick_index
            if tick_index >= len(catalog["depth"]) - 1:
                run.status = "completed"
                run.completed_at = utcnow()
            append_audit(
                db,
                action="scenario.tick.processed",
                resource_type="scenario_run",
                resource_id=run.id,
                site_id=site.id,
                detail={
                    "tickIndex": tick_index,
                    "maxDepthCm": depth,
                    "rainfallMmH": rainfall,
                    "forecastRunId": forecast.id,
                    "qualityStatus": quality_status,
                },
                actor_type="service",
                actor_id="scenario-engine",
                trace_id=forecast.trace_id,
                occurred_at=event_time,
            )
            db.commit()
            payload = {
                "runId": run.id,
                "status": run.status,
                "tickIndex": tick_index,
                "simulatedMinutes": tick_index,
                "siteId": site.id,
                "eventTime": event_time.isoformat(),
                "waterState": {
                    "maxDepthCm": water.max_depth_cm,
                    "avgDepthCm": water.avg_depth_cm,
                    "areaM2": water.area_m2,
                    "confidence": round(water.confidence * 100, 1),
                    "qualityStatus": water.quality_status,
                },
                "weather": {"rainfallMmH": rainfall, "condition": weather.condition},
                "forecast": {
                    "id": forecast.id,
                    "riskLevel": forecast.risk_level,
                    "confidence": forecast.confidence,
                    "reachRiskMinutes": forecast.reach_risk_minutes,
                },
                "alertId": alert.id if alert else None,
            }

        # Publishing is scheduled outside DB transaction. This sync method can be
        # called from an async context, so use create_task rather than blocking it.
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broker.publish("scenario.tick", payload))
        except RuntimeError:
            pass
        return payload

    def _upsert_alert_and_action(
        self,
        db: Session,
        run: ScenarioRun,
        site: Site,
        forecast: ForecastRun,
        event_time: datetime,
    ) -> Alert | None:
        if forecast.risk_level == "normal" and forecast.reach_risk_minutes is None:
            return None
        alert = db.scalar(
            select(Alert)
            .where(
                Alert.scenario_run_id == run.id,
                Alert.status.in_(["open", "acknowledged"]),
            )
            .order_by(Alert.created_at.desc())
            .limit(1)
        )
        level = "critical" if forecast.risk_level == "critical" else "high" if forecast.risk_level == "high" else "attention"
        if alert is None:
            alert = Alert(
                id=f"alert-{uuid4().hex[:16]}",
                site_id=site.id,
                forecast_run_id=forecast.id,
                scenario_run_id=run.id,
                created_at=event_time,
                updated_at=event_time,
                level=level,
                status="open",
                title=f"{site.short_name}积水趋势预警",
                message=f"预计 {forecast.reach_risk_minutes or 0:.0f} 分钟后达到风险线，建议复核联动措施。",
                threshold_depth_cm=site.risk_threshold_cm,
                eta_minutes=forecast.reach_risk_minutes,
                confidence=forecast.confidence,
                action_required=forecast.confidence >= 85,
                dedupe_key=f"{run.id}:{site.id}:risk-threshold",
                source="scenario-forecast",
            )
            db.add(alert)
            db.flush()
        else:
            alert.forecast_run_id = forecast.id
            alert.updated_at = event_time
            alert.level = level
            alert.eta_minutes = forecast.reach_risk_minutes
            alert.confidence = forecast.confidence
            alert.message = f"预测已更新：当前置信度 {forecast.confidence:.0f}%，请持续关注。"

        auto_eligible = (
            forecast.confidence >= 85
            and forecast.reach_risk_minutes is not None
            and forecast.reach_risk_minutes <= 30
        )
        if auto_eligible:
            existing_action = db.scalar(
                select(ActionRecord)
                .where(
                    ActionRecord.scenario_run_id == run.id,
                    ActionRecord.action_type == "close_gate",
                    ActionRecord.status.in_(["pending", "confirmed", "dispatched", "acked"]),
                )
                .limit(1)
            )
            gate = db.scalar(
                select(Device).where(Device.site_id == site.id, Device.device_type == "gate").limit(1)
            )
            if existing_action is None and gate is not None:
                db.add(
                    ActionRecord(
                        id=f"action-{uuid4().hex[:16]}",
                        site_id=site.id,
                        alert_id=alert.id,
                        scenario_run_id=run.id,
                        action_type="close_gate",
                        target_type="device",
                        target_id=gate.id,
                        status="pending",
                        priority="critical",
                        requested_at=event_time,
                        requested_by="policy-engine",
                        expires_at=event_time + timedelta(minutes=10),
                        idempotency_key=f"{run.id}:close-gate",
                        command_payload={
                            "schemaVersion": 1,
                            "command": "close",
                            "targetState": "closed",
                            "ttlSeconds": 600,
                            "interlocks": ["vehiclePresent=false", "safetyLoop=ok"],
                        },
                    )
                )
        return alert
