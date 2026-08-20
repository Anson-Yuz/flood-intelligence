from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class APIModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
        serialize_by_alias=True,
    )


class HealthResponse(APIModel):
    status: str
    service: str
    version: str
    database: str
    seeded: bool
    timestamp: datetime


class DeviceRead(APIModel):
    id: str
    site_id: str
    station_id: str
    name: str
    device_type: str
    vendor: str
    model: str
    protocol: str
    status: str
    firmware_version: str
    last_seen_at: datetime
    capabilities: list[str]
    telemetry: dict[str, Any]


class WeatherRead(APIModel):
    id: int
    site_id: str
    observed_at: datetime
    condition: str
    rainfall_mm_h: float
    forecast_15m_mm: float
    forecast_30m_mm: float
    forecast_60m_mm: float
    temperature_c: float
    humidity_pct: float
    wind_m_s: float
    source: str
    confidence: float


class WaterStateRead(APIModel):
    id: int
    site_id: str
    observed_at: datetime
    avg_depth_cm: float
    max_depth_cm: float
    area_m2: float
    volume_m3: float
    depth_segments_cm: list[float]
    slope_1m_cm_min: float
    slope_5m_cm_min: float
    slope_10m_cm_min: float
    drainage_saturation: str
    confidence: float
    quality_status: str
    quality_flags: list[str]
    dem_version: str
    model_version: str
    source: str


class ForecastPointRead(APIModel):
    horizon_minutes: int
    predicted_depth_cm: float
    lower_depth_cm: float
    upper_depth_cm: float
    confidence: float
    risk_level: str


class ForecastRunRead(APIModel):
    id: str
    site_id: str
    created_at: datetime
    status: str
    trigger_type: str
    current_depth_cm: float
    base_slope_cm_min: float
    corrected_slope_cm_min: float
    risk_level: str
    reach_risk_minutes: float | None
    reach_closure_minutes: float | None
    confidence: float
    rules_version: str
    model_version: str
    dem_version: str
    summary: str
    trace_id: str
    points: list[ForecastPointRead] = Field(default_factory=list)


class SiteSummary(APIModel):
    id: str
    name: str
    short_name: str
    site_type: str
    district: str
    address: str
    latitude: float
    longitude: float
    coverage_area_m2: float
    status: str
    current_mode: str
    risk_level: str
    risk_threshold_cm: float
    closure_threshold_cm: float
    latest_water: WaterStateRead | None = None
    latest_weather: WeatherRead | None = None
    latest_forecast: ForecastRunRead | None = None
    active_alert_count: int = 0
    online_device_count: int = 0
    device_count: int = 0


class SiteDetail(SiteSummary):
    catchment_area_m2: float
    drainage_capacity_m3_min: float
    dem_version: str
    calibration_version: str
    description: str
    tags: list[str]
    devices: list[DeviceRead] = Field(default_factory=list)
    water_history: list[WaterStateRead] = Field(default_factory=list)


class AlertRead(APIModel):
    id: str
    site_id: str
    forecast_run_id: str | None
    created_at: datetime
    updated_at: datetime
    level: str
    status: str
    title: str
    message: str
    threshold_depth_cm: float | None
    eta_minutes: float | None
    confidence: float
    action_required: bool
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    source: str


class InferenceStepRead(APIModel):
    id: int
    forecast_run_id: str
    step_order: int
    layer: str
    name: str
    status: str
    started_at: datetime
    duration_ms: int
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    rationale: str


class ActionRead(APIModel):
    id: str
    site_id: str
    alert_id: str | None
    action_type: str
    target_type: str
    target_id: str
    status: str
    priority: str
    requested_at: datetime
    requested_by: str
    decided_at: datetime | None
    decided_by: str | None
    decision_reason: str | None
    dispatched_at: datetime | None
    acknowledged_at: datetime | None
    expires_at: datetime | None
    idempotency_key: str
    command_payload: dict[str, Any]
    edge_response: dict[str, Any]


class AuditLogRead(APIModel):
    id: int
    tenant_id: str
    site_id: str | None
    occurred_at: datetime
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    trace_id: str
    detail: dict[str, Any]
    previous_hash: str
    entry_hash: str


class ReviewDetail(APIModel):
    forecast: ForecastRunRead
    site: SiteSummary
    inference_steps: list[InferenceStepRead]
    related_alerts: list[AlertRead]
    related_actions: list[ActionRead]
    audit_trail: list[AuditLogRead]
    input_snapshot: dict[str, Any]
    physics_checks: list[dict[str, Any]]


class ActionDecision(APIModel):
    actor_id: str = Field(default="demo-operator", min_length=2, max_length=80)
    reason: str = Field(default="值班人员已复核", max_length=500)


class ScenarioStartRequest(APIModel):
    site_id: str = "site-binh-rd-tunnel"
    speed: float = Field(default=1.0, ge=0.25, le=20.0)
    auto_run: bool = True


class ScenarioRunRead(APIModel):
    id: str
    scenario_key: str
    site_id: str
    status: str
    tick_index: int
    simulated_minutes: int
    speed: float
    seed: int
    started_at: datetime | None
    paused_at: datetime | None
    reset_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    config: dict[str, Any]


class EdgeTelemetryEnvelope(APIModel):
    event_id: str = Field(min_length=8, max_length=100)
    schema_version: int = Field(default=1, ge=1)
    event_type: Literal["water.state", "weather.snapshot"]
    tenant_id: str = "demo-tenant"
    site_id: str
    station_id: str
    device_id: str
    event_time: datetime
    sequence_no: int = Field(ge=0)
    trace_id: str | None = None
    refs: dict[str, str] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any]

    @field_validator("event_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("eventTime must include a timezone")
        return value


class EdgeEventSource(APIModel):
    tenant_id: str
    edge_node_id: str


class EdgeEventSubject(APIModel):
    site_id: str
    station_id: str
    point_id: str | None = None


class EdgeEventQuality(APIModel):
    status: str = "good"
    confidence: float = Field(default=1.0, ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class EdgeUnifiedEnvelope(APIModel):
    """Canonical envelope emitted by the Ubuntu edge runtime."""

    schema_version: Literal["yujian.edge.event/v1"]
    event_id: str = Field(min_length=8, max_length=100)
    event_type: str = Field(min_length=3, max_length=80)
    occurred_at: datetime
    produced_at: datetime
    sequence: int = Field(ge=0)
    trace_id: str
    source: EdgeEventSource
    subject: EdgeEventSubject
    quality: EdgeEventQuality
    context: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any]

    @field_validator("occurred_at", "produced_at")
    @classmethod
    def require_envelope_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("edge envelope timestamps must include a timezone")
        return value


class EdgeHeartbeat(APIModel):
    station_id: str
    device_id: str
    site_id: str
    event_time: datetime
    firmware_version: str | None = None
    status: str = "online"
    telemetry: dict[str, Any] = Field(default_factory=dict)


class EdgeCommandAck(APIModel):
    station_id: str
    status: Literal["acked", "verified", "failed"]
    acknowledged_at: datetime
    device_state: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
