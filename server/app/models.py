from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, default="demo-tenant")
    username: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40), default="viewer")
    region_scope: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    salt: Mapped[str | None] = mapped_column(String(64), nullable=True)
    iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_session_user_expiry", "user_id", "expires_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remember: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, default="demo-tenant")
    name: Mapped[str] = mapped_column(String(160), index=True)
    short_name: Mapped[str] = mapped_column(String(80))
    site_type: Mapped[str] = mapped_column(String(40), default="road")
    district: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(240))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    coverage_area_m2: Mapped[float] = mapped_column(Float, default=750.0)
    catchment_area_m2: Mapped[float] = mapped_column(Float, default=2400.0)
    drainage_capacity_m3_min: Mapped[float] = mapped_column(Float, default=1.8)
    risk_threshold_cm: Mapped[float] = mapped_column(Float, default=30.0)
    closure_threshold_cm: Mapped[float] = mapped_column(Float, default=40.0)
    status: Mapped[str] = mapped_column(String(32), default="online", index=True)
    current_mode: Mapped[str] = mapped_column(String(32), default="rain")
    risk_level: Mapped[str] = mapped_column(String(24), default="normal", index=True)
    dem_version: Mapped[str] = mapped_column(String(40), default="dem-v1")
    calibration_version: Mapped[str] = mapped_column(String(40), default="cal-v1")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    devices: Mapped[list["Device"]] = relationship(back_populates="site")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (Index("ix_device_site_type", "site_id", "device_type"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    station_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    device_type: Mapped[str] = mapped_column(String(40))
    vendor: Mapped[str] = mapped_column(String(80), default="Yujian")
    model: Mapped[str] = mapped_column(String(80), default="Edge-Sim")
    protocol: Mapped[str] = mapped_column(String(40), default="mqtt")
    status: Mapped[str] = mapped_column(String(24), default="online", index=True)
    firmware_version: Mapped[str] = mapped_column(String(40), default="1.0.0")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    telemetry: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    desired_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reported_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    site: Mapped[Site] = relationship(back_populates="devices")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"
    __table_args__ = (Index("ix_weather_site_time", "site_id", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    scenario_run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    condition: Mapped[str] = mapped_column(String(40), default="heavy_rain")
    rainfall_mm_h: Mapped[float] = mapped_column(Float, default=0.0)
    forecast_15m_mm: Mapped[float] = mapped_column(Float, default=0.0)
    forecast_30m_mm: Mapped[float] = mapped_column(Float, default=0.0)
    forecast_60m_mm: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_c: Mapped[float] = mapped_column(Float, default=24.0)
    humidity_pct: Mapped[float] = mapped_column(Float, default=80.0)
    wind_m_s: Mapped[float] = mapped_column(Float, default=2.0)
    source: Mapped[str] = mapped_column(String(80), default="municipal-weather-sim")
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class WaterState(Base):
    __tablename__ = "water_states"
    __table_args__ = (Index("ix_water_site_time", "site_id", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    scenario_run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_depth_cm: Mapped[float] = mapped_column(Float, default=0.0)
    max_depth_cm: Mapped[float] = mapped_column(Float, default=0.0)
    area_m2: Mapped[float] = mapped_column(Float, default=0.0)
    volume_m3: Mapped[float] = mapped_column(Float, default=0.0)
    depth_segments_cm: Mapped[list[float]] = mapped_column(JSON, default=list)
    slope_1m_cm_min: Mapped[float] = mapped_column(Float, default=0.0)
    slope_5m_cm_min: Mapped[float] = mapped_column(Float, default=0.0)
    slope_10m_cm_min: Mapped[float] = mapped_column(Float, default=0.0)
    drainage_saturation: Mapped[str] = mapped_column(String(24), default="green")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    quality_status: Mapped[str] = mapped_column(String(24), default="accepted")
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    dem_version: Mapped[str] = mapped_column(String(40), default="dem-v1")
    calibration_version: Mapped[str] = mapped_column(String(40), default="cal-v1")
    model_version: Mapped[str] = mapped_column(String(40), default="reflection-v0.4")
    boundary_geojson: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(40), default="edge")
    event_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    __table_args__ = (Index("ix_forecast_site_created", "site_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    scenario_run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(24), default="valid")
    trigger_type: Mapped[str] = mapped_column(String(40), default="scheduled")
    current_depth_cm: Mapped[float] = mapped_column(Float)
    base_slope_cm_min: Mapped[float] = mapped_column(Float)
    corrected_slope_cm_min: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(24), default="normal")
    reach_risk_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    reach_closure_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    rules_version: Mapped[str] = mapped_column(String(40), default="rules-v5.1-demo")
    model_version: Mapped[str] = mapped_column(String(40), default="reflection-v0.4")
    dem_version: Mapped[str] = mapped_column(String(40), default="dem-v1")
    calibration_version: Mapped[str] = mapped_column(String(40), default="cal-v1")
    weather_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    supersedes_forecast_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(80), index=True)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    physics_checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    points: Mapped[list["ForecastPoint"]] = relationship(
        back_populates="forecast_run", cascade="all, delete-orphan", order_by="ForecastPoint.horizon_minutes"
    )
    steps: Mapped[list["InferenceStep"]] = relationship(
        back_populates="forecast_run", cascade="all, delete-orphan", order_by="InferenceStep.step_order"
    )


class ForecastPoint(Base):
    __tablename__ = "forecast_points"
    __table_args__ = (
        UniqueConstraint("forecast_run_id", "horizon_minutes", name="uq_forecast_horizon"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_run_id: Mapped[str] = mapped_column(ForeignKey("forecast_runs.id"), index=True)
    horizon_minutes: Mapped[int] = mapped_column(Integer)
    predicted_depth_cm: Mapped[float] = mapped_column(Float)
    lower_depth_cm: Mapped[float] = mapped_column(Float)
    upper_depth_cm: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(24), default="normal")

    forecast_run: Mapped[ForecastRun] = relationship(back_populates="points")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_site_status", "site_id", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    forecast_run_id: Mapped[str | None] = mapped_column(ForeignKey("forecast_runs.id"), nullable=True)
    scenario_run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    level: Mapped[str] = mapped_column(String(24), default="attention", index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    threshold_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    eta_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    action_required: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), index=True)
    source: Mapped[str] = mapped_column(String(40), default="forecast")


class InferenceStep(Base):
    __tablename__ = "inference_steps"
    __table_args__ = (UniqueConstraint("forecast_run_id", "step_order", name="uq_inference_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_run_id: Mapped[str] = mapped_column(ForeignKey("forecast_runs.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    layer: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="passed")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(Text, default="")

    forecast_run: Mapped[ForecastRun] = relationship(back_populates="steps")


class ActionRecord(Base):
    __tablename__ = "action_records"
    __table_args__ = (Index("ix_action_site_status", "site_id", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    alert_id: Mapped[str | None] = mapped_column(ForeignKey("alerts.id"), nullable=True)
    scenario_run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    action_type: Mapped[str] = mapped_column(String(48))
    target_type: Mapped[str] = mapped_column(String(40), default="device")
    target_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(24), default="high")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    requested_by: Mapped[str] = mapped_column(String(80), default="system")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    command_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    edge_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_tenant_time", "tenant_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, default="demo-tenant")
    site_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="system")
    actor_id: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[str] = mapped_column(String(100))
    trace_id: Mapped[str] = mapped_column(String(80), index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64), default="GENESIS")
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    __table_args__ = (Index("ix_scenario_key_status", "scenario_key", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_key: Mapped[str] = mapped_column(String(80), index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    tick_index: Mapped[int] = mapped_column(Integer, default=0)
    simulated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    seed: Mapped[int] = mapped_column(Integer, default=5101)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
