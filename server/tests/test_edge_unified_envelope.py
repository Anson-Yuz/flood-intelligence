from __future__ import annotations

from datetime import datetime, timezone


def _unified_event(event_id: str = "edge-water-unified-0001") -> dict:
    event_time = datetime.now(timezone.utc).isoformat()
    return {
        "schemaVersion": "yujian.edge.event/v1",
        "eventId": event_id,
        "eventType": "water.state.v1",
        "occurredAt": event_time,
        "producedAt": event_time,
        "sequence": 1043,
        "traceId": "ce0c23fd-7a61-4be8-8288-82a73b69dfcb",
        "source": {"tenantId": "demo-tenant", "edgeNodeId": "edge-ubuntu-001"},
        "subject": {
            "siteId": "site-binh-rd-tunnel",
            "stationId": "station-binh-rd-tunnel",
            "pointId": "low-point-a",
        },
        "quality": {"status": "good", "confidence": 0.91, "reasons": []},
        "context": {
            "configVersion": "pilot-2026-07-10",
            "adapter": "SiteCameraAdapter",
            "adapterVersion": "site-v1",
            "cameraCalibrationVersion": "camera-cal-20260701",
            "demVersion": "dem-bh-20260701-v17",
            "mock": False,
        },
        "payload": {
            "state": "rising",
            "averageDepthCm": 12.6,
            "maxDepthCm": 18.4,
            "areaM2": 106.5,
            "volumeM3": 7.38,
            "riseRateCmPerMin": 1.4,
            "demVersion": "dem-bh-20260701-v17",
            "observationWindowSeconds": 5,
        },
    }


def test_accepts_edge_runtime_unified_water_envelope(client):
    envelope = _unified_event()
    response = client.post("/api/v1/edge/v1/telemetry", json=envelope)
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["duplicate"] is False
    assert payload["eventType"] == "water.state.v1"
    assert payload["forecastRunId"]

    site = client.get("/api/v1/sites/site-binh-rd-tunnel").json()
    latest = site["latestWater"]
    assert latest["avgDepthCm"] == 12.6
    assert latest["maxDepthCm"] == 18.4
    assert latest["slope5mCmMin"] == 1.4
    assert latest["confidence"] == 0.91
    assert latest["qualityStatus"] == "accepted"

    replay = client.post("/api/v1/edge/v1/telemetry", json=envelope)
    assert replay.status_code == 202
    assert replay.json()["duplicate"] is True


def test_accepts_unified_heartbeat_on_telemetry_endpoint(client):
    heartbeat = _unified_event("edge-heartbeat-unified-0001")
    heartbeat["eventType"] = "edge.heartbeat.v1"
    heartbeat["sequence"] = 1044
    heartbeat["payload"] = {
        "status": "online",
        "mode": "rain_monitor",
        "uptimeSeconds": 86412.2,
        "outbox": {"pending": 0, "maxAttempts": 0},
        "clock": {"utc": "2026-07-10T08:30:05.000Z", "synchronized": True},
    }
    response = client.post("/api/v1/edge/v1/telemetry", json=heartbeat)
    assert response.status_code == 202, response.text
    assert response.json()["eventType"] == "edge.heartbeat.v1"

    devices = client.get(
        "/api/v1/devices",
        params={"site_id": "site-binh-rd-tunnel", "device_type": "gateway"},
    ).json()
    assert devices[0]["telemetry"]["edgeRuntime"]["mode"] == "rain_monitor"
