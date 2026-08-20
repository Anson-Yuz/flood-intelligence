from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import append_audit
from .inference import create_forecast_run, risk_level_for_depth
from .models import (
    ActionRecord,
    Alert,
    Device,
    Site,
    User,
    WaterState,
    WeatherSnapshot,
    utcnow,
)


SITE_FIXTURES = [
    {
        "id": "site-binh-rd-tunnel",
        "name": "滨河路下穿隧道",
        "short_name": "滨河路隧道",
        "site_type": "underpass",
        "district": "滨江区",
        "address": "滨河路与汀兰路交叉口下穿段",
        "latitude": 30.23082,
        "longitude": 120.16491,
        "coverage_area_m2": 748.0,
        "catchment_area_m2": 2860.0,
        "drainage_capacity_m3_min": 1.65,
        "risk_threshold_cm": 30.0,
        "closure_threshold_cm": 40.0,
        "status": "online",
        "current_mode": "rain",
        "risk_level": "high",
        "dem_version": "dem-bh-20260701-v17",
        "calibration_version": "cal-bh-v9",
        "description": "U 型下穿隧道最低点，暴雨时车辆无法掉头，为本次演示主监测点。",
        "tags": ["重点易涝点", "自动联动", "路灯杆挂载"],
        "sort_order": 1,
    },
    {
        "id": "site-oldtown-south",
        "name": "老城南路低洼路段",
        "short_name": "老城南路",
        "site_type": "low_road",
        "district": "老城区",
        "address": "老城南路 217 号至 245 号",
        "latitude": 30.22416,
        "longitude": 120.14981,
        "coverage_area_m2": 612.0,
        "catchment_area_m2": 1980.0,
        "drainage_capacity_m3_min": 1.12,
        "risk_threshold_cm": 25.0,
        "closure_threshold_cm": 35.0,
        "status": "online",
        "current_mode": "rain",
        "risk_level": "attention",
        "dem_version": "dem-ln-20260628-v08",
        "calibration_version": "cal-ln-v5",
        "description": "老旧沉降路段，持续跟踪路面劣化和积水边界。",
        "tags": ["沉降监测", "重点养护"],
        "sort_order": 2,
    },
    {
        "id": "site-yunqi-garage",
        "name": "云栖花园地下车库入口",
        "short_name": "云栖车库",
        "site_type": "garage",
        "district": "云栖区",
        "address": "云栖花园东门地下车库坡道",
        "latitude": 30.21871,
        "longitude": 120.17825,
        "coverage_area_m2": 386.0,
        "catchment_area_m2": 920.0,
        "drainage_capacity_m3_min": 0.88,
        "risk_threshold_cm": 20.0,
        "closure_threshold_cm": 30.0,
        "status": "online",
        "current_mode": "rain",
        "risk_level": "normal",
        "dem_version": "dem-yq-20260702-v04",
        "calibration_version": "cal-yq-v3",
        "description": "物业侧地下车库入口，联动挡水板和值守人员。",
        "tags": ["物业联动", "车库入口"],
        "sort_order": 3,
    },
    {
        "id": "site-tech-avenue-pit",
        "name": "科创大道施工基坑",
        "short_name": "科创基坑",
        "site_type": "construction_pit",
        "district": "高新区",
        "address": "科创大道综合管廊二标段",
        "latitude": 30.24153,
        "longitude": 120.19102,
        "coverage_area_m2": 752.0,
        "catchment_area_m2": 2240.0,
        "drainage_capacity_m3_min": 2.05,
        "risk_threshold_cm": 35.0,
        "closure_threshold_cm": 50.0,
        "status": "degraded",
        "current_mode": "rain",
        "risk_level": "attention",
        "dem_version": "dem-kc-20260621-v12",
        "calibration_version": "cal-kc-v7",
        "description": "施工期临时监测点，边缘网关处于弱网降级状态。",
        "tags": ["施工场景", "弱网兜底"],
        "sort_order": 4,
    },
]


def _device(
    site_id: str,
    suffix: str,
    name: str,
    device_type: str,
    capabilities: list[str],
    *,
    status: str = "online",
    protocol: str = "mqtt",
    telemetry: dict[str, object] | None = None,
) -> Device:
    return Device(
        id=f"dev-{site_id.removeprefix('site-')}-{suffix}",
        site_id=site_id,
        station_id=f"station-{site_id.removeprefix('site-')}",
        name=name,
        device_type=device_type,
        vendor="预鉴科技",
        model={
            "camera": "YJ-CAM-1080P",
            "lidar": "YJ-L16",
            "rain_gauge": "YJ-RG1",
            "gateway": "YJ-EDGE-A1",
            "gate": "YJ-GATE-IO",
            "led": "YJ-LED-P8",
        }.get(device_type, "YJ-SIM"),
        protocol=protocol,
        status=status,
        firmware_version="1.6.2" if device_type == "gateway" else "1.3.8",
        last_seen_at=utcnow(),
        capabilities=capabilities,
        telemetry=telemetry or {"signalRssi": -61, "temperatureC": 42.1},
        desired_config={"reportIntervalSec": 5, "offlineBufferHours": 72},
        reported_config={"reportIntervalSec": 5, "offlineBufferHours": 72},
    )


def seed_database(db: Session) -> bool:
    if (db.scalar(select(func.count()).select_from(Site)) or 0) > 0:
        return False

    now = utcnow().replace(second=0, microsecond=0)
    db.add_all(
        [
            User(
                tenant_id="demo-tenant",
                username="operator",
                display_name="陈晓雨",
                role="dispatcher",
                region_scope=["滨江区", "老城区", "云栖区", "高新区"],
            ),
            User(
                tenant_id="demo-tenant",
                username="auditor",
                display_name="周正",
                role="auditor",
                region_scope=["*"],
            ),
        ]
    )
    sites = [Site(**fixture) for fixture in SITE_FIXTURES]
    db.add_all(sites)
    db.flush()

    for site in sites:
        degraded = site.status == "degraded"
        db.add_all(
            [
                _device(site.id, "camera", "雨滴反光分析相机", "camera", ["rtsp", "reflection-analysis"]),
                _device(site.id, "lidar", "间歇式多线激光雷达", "lidar", ["point-cloud", "dem-scan"]),
                _device(site.id, "rain", "翻斗式雨量计", "rain_gauge", ["rainfall-mm-h"], protocol="modbus"),
                _device(
                    site.id,
                    "edge",
                    "Ubuntu 边缘计算网关",
                    "gateway",
                    ["store-forward", "onnx-runtime", "offline-rule"],
                    status="degraded" if degraded else "online",
                    telemetry={
                        "cpuPct": 34.2 if not degraded else 62.8,
                        "memoryPct": 47.1,
                        "diskPct": 31.0,
                        "signalRssi": -63 if not degraded else -91,
                        "bufferedEvents": 0 if not degraded else 187,
                    },
                ),
            ]
        )
    db.add_all(
        [
            _device(
                "site-binh-rd-tunnel",
                "gate",
                "隧道入口道闸",
                "gate",
                ["close", "open", "position-feedback", "vehicle-interlock"],
                protocol="modbus-tcp",
                telemetry={"position": "open", "vehiclePresent": False, "safetyLoop": "ok"},
            ),
            _device(
                "site-binh-rd-tunnel",
                "led",
                "入口诱导 LED 屏",
                "led",
                ["text", "severity-color", "flash"],
                protocol="http",
                telemetry={"display": "暴雨天气 请减速慢行", "brightnessPct": 76},
            ),
        ]
    )

    site_values = {
        "site-binh-rd-tunnel": {
            "rain": 36.0,
            "depth": 22.8,
            "slope": 0.66,
            "area": 318.0,
            "conf": 0.94,
            "saturation": "red",
        },
        "site-oldtown-south": {
            "rain": 24.0,
            "depth": 14.6,
            "slope": 0.31,
            "area": 188.0,
            "conf": 0.91,
            "saturation": "yellow",
        },
        "site-yunqi-garage": {
            "rain": 12.0,
            "depth": 5.2,
            "slope": 0.08,
            "area": 52.0,
            "conf": 0.93,
            "saturation": "green",
        },
        "site-tech-avenue-pit": {
            "rain": 28.0,
            "depth": 19.4,
            "slope": 0.25,
            "area": 226.0,
            "conf": 0.72,
            "saturation": "yellow",
        },
    }
    latest_states: dict[str, WaterState] = {}
    latest_weather: dict[str, WeatherSnapshot] = {}
    for site in sites:
        values = site_values[site.id]
        for minutes_ago in range(30, -1, -5):
            progress = (30 - minutes_ago) / 30
            max_depth = max(0.2, values["depth"] - values["slope"] * minutes_ago * 0.73)
            avg_depth = max_depth * 0.62
            area = values["area"] * (0.55 + progress * 0.45)
            water = WaterState(
                site_id=site.id,
                observed_at=now - timedelta(minutes=minutes_ago),
                sequence_no=5000 + (30 - minutes_ago),
                avg_depth_cm=round(avg_depth, 2),
                max_depth_cm=round(max_depth, 2),
                area_m2=round(area, 2),
                volume_m3=round(area * avg_depth / 100, 2),
                depth_segments_cm=[
                    round(max_depth * factor, 2) for factor in (0.34, 0.68, 1.0, 0.76, 0.41)
                ],
                slope_1m_cm_min=round(values["slope"] * 1.06, 3),
                slope_5m_cm_min=round(values["slope"], 3),
                slope_10m_cm_min=round(values["slope"] * 0.91, 3),
                drainage_saturation=values["saturation"],
                confidence=values["conf"],
                quality_status="accepted",
                quality_flags=["WEAK_NETWORK"] if site.status == "degraded" else [],
                dem_version=site.dem_version,
                calibration_version=site.calibration_version,
                model_version="reflection-v0.4.2",
                boundary_geojson={
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [10, 0], [12, 7], [2, 9], [0, 0]]],
                },
                source="edge-simulator",
                event_id=f"seed-{site.id}-{minutes_ago}",
            )
            db.add(water)
            if minutes_ago == 0:
                latest_states[site.id] = water

        weather = WeatherSnapshot(
            site_id=site.id,
            observed_at=now,
            issued_at=now - timedelta(minutes=3),
            condition="heavy_rain" if values["rain"] >= 25 else "moderate_rain",
            rainfall_mm_h=values["rain"],
            forecast_15m_mm=round(values["rain"] * 0.25 * 1.08, 1),
            forecast_30m_mm=round(values["rain"] * 0.5 * 0.96, 1),
            forecast_60m_mm=round(values["rain"] * 0.78, 1),
            temperature_c=23.8,
            humidity_pct=93.0,
            wind_m_s=3.6,
            source="市气象局短临网格（模拟）",
            confidence=0.92 if site.status == "online" else 0.78,
            raw_payload={"gridId": "HZ-120-64", "isSimulated": True},
        )
        db.add(weather)
        latest_weather[site.id] = weather
    db.flush()

    forecasts = {}
    for site in sites:
        forecasts[site.id] = create_forecast_run(
            db,
            site=site,
            water_state=latest_states[site.id],
            weather=latest_weather[site.id],
            trigger_type="seed",
            created_at=now,
        )
    db.flush()

    main_site = next(item for item in sites if item.id == "site-binh-rd-tunnel")
    main_forecast = forecasts[main_site.id]
    main_alert = Alert(
        id="alert-bh-001",
        site_id=main_site.id,
        forecast_run_id=main_forecast.id,
        created_at=now,
        updated_at=now,
        level="high",
        status="open",
        title="滨河路隧道积水预计进入高风险区",
        message=(
            f"当前最大水深 {latest_states[main_site.id].max_depth_cm:.1f} cm，"
            f"预计 {main_forecast.reach_risk_minutes:.0f} 分钟后达到 30 cm 风险线。"
        ),
        threshold_depth_cm=30.0,
        eta_minutes=main_forecast.reach_risk_minutes,
        confidence=main_forecast.confidence,
        action_required=True,
        dedupe_key=f"{main_site.id}:depth:30",
        source="forecast",
    )
    db.add(main_alert)
    db.flush()
    action = ActionRecord(
        id="action-bh-gate-001",
        site_id=main_site.id,
        alert_id=main_alert.id,
        action_type="close_gate",
        target_type="device",
        target_id="dev-binh-rd-tunnel-gate",
        status="pending",
        priority="critical",
        requested_at=now,
        requested_by="policy-engine",
        expires_at=now + timedelta(minutes=20),
        idempotency_key="seed-bh-close-gate-001",
        command_payload={
            "schemaVersion": 1,
            "command": "close",
            "targetState": "closed",
            "ttlSeconds": 1200,
            "interlocks": ["vehiclePresent=false", "safetyLoop=ok"],
            "message": "前方积水，请绕行",
        },
    )
    db.add(action)

    old_site = next(item for item in sites if item.id == "site-oldtown-south")
    db.add(
        Alert(
            id="alert-ln-001",
            site_id=old_site.id,
            forecast_run_id=forecasts[old_site.id].id,
            created_at=now - timedelta(minutes=4),
            updated_at=now - timedelta(minutes=4),
            level="attention",
            status="open",
            title="老城南路排水能力接近饱和",
            message="上涨斜率连续 10 分钟为正，建议增加巡查频次。",
            threshold_depth_cm=old_site.risk_threshold_cm,
            eta_minutes=forecasts[old_site.id].reach_risk_minutes,
            confidence=forecasts[old_site.id].confidence,
            action_required=False,
            dedupe_key=f"{old_site.id}:drainage:yellow",
            source="state-analysis",
        )
    )

    append_audit(
        db,
        action="platform.seeded",
        resource_type="platform",
        resource_id="demo",
        detail={"siteCount": 4, "source": "V5.1 demo fixtures"},
        actor_type="system",
        actor_id="seed-service",
        trace_id=f"trace-seed-{uuid4().hex[:10]}",
        occurred_at=now - timedelta(minutes=8),
    )
    append_audit(
        db,
        action="forecast.published",
        resource_type="forecast_run",
        resource_id=main_forecast.id,
        site_id=main_site.id,
        detail={
            "confidence": main_forecast.confidence,
            "ruleVersion": main_forecast.rules_version,
            "demVersion": main_forecast.dem_version,
        },
        actor_type="service",
        actor_id="forecast-engine",
        trace_id=main_forecast.trace_id,
        occurred_at=now,
    )
    append_audit(
        db,
        action="action.proposed",
        resource_type="action_record",
        resource_id=action.id,
        site_id=main_site.id,
        detail={"type": action.action_type, "targetId": action.target_id, "status": action.status},
        actor_type="service",
        actor_id="policy-engine",
        trace_id=main_forecast.trace_id,
        occurred_at=now,
    )

    for site in sites:
        site.risk_level = risk_level_for_depth(site, latest_states[site.id].max_depth_cm)
        if forecasts[site.id].risk_level in {"high", "critical"}:
            site.risk_level = forecasts[site.id].risk_level

    db.commit()
    return True
