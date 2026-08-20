from __future__ import annotations

from datetime import datetime, timezone


def test_health_dashboard_and_seed_data(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["seeded"] is True

    sites = client.get("/api/v1/sites")
    assert sites.status_code == 200
    site_rows = sites.json()
    assert len(site_rows) == 4
    assert site_rows[0]["id"] == "site-binh-rd-tunnel"
    assert site_rows[0]["latestWater"]["maxDepthCm"] == 22.8

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["overview"]["siteCount"] == 4
    assert payload["overview"]["activeAlertCount"] >= 2
    assert payload["primarySite"]["shortName"] == "滨河路隧道"
    assert len(payload["forecastCurve"]) == 6


def test_review_detail_contains_auditable_l1_l4_trace(client):
    forecast = client.get("/api/v1/sites/site-binh-rd-tunnel/forecast")
    assert forecast.status_code == 200
    forecast_id = forecast.json()["id"]

    review = client.get(f"/api/v1/reviews/{forecast_id}")
    assert review.status_code == 200
    payload = review.json()
    assert payload["forecast"]["rulesVersion"] == "rules-v5.1-demo.3"
    assert [step["layer"] for step in payload["inferenceSteps"]] == [
        "L1",
        "L2",
        "L3",
        "L3",
        "L3",
        "L3",
        "L4",
    ]
    assert all(item["status"] == "passed" for item in payload["physicsChecks"])
    assert payload["inputSnapshot"]["caseIds"]


def test_action_confirm_edge_dispatch_and_ack(client):
    pending = client.get("/api/v1/actions", params={"status": "pending"})
    assert pending.status_code == 200
    action = pending.json()[0]

    confirmed = client.post(
        f"/api/v1/actions/{action['id']}/confirm",
        json={"actorId": "operator", "reason": "现场画面与入口联锁复核通过"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    commands = client.get("/api/v1/edge/v1/stations/station-binh-rd-tunnel/commands")
    assert commands.status_code == 200
    assert commands.json()[0]["status"] == "dispatched"
    assert commands.json()[0]["commandPayload"]["command"] == "close"

    ack = client.post(
        f"/api/v1/edge/v1/commands/{action['id']}/ack",
        json={
            "stationId": "station-binh-rd-tunnel",
            "status": "verified",
            "acknowledgedAt": datetime.now(timezone.utc).isoformat(),
            "deviceState": {"position": "closed", "safetyLoop": "ok"},
            "message": "道闸已关闭并完成位置核验",
        },
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "verified"
    assert ack.json()["edgeResponse"]["deviceState"]["position"] == "closed"

    audit = client.get("/api/v1/audit/verify")
    assert audit.status_code == 200
    assert audit.json()["valid"] is True
    assert audit.json()["checked"] >= 6


def test_reject_is_persisted_and_cannot_be_replayed(client):
    action_id = client.get("/api/v1/actions", params={"status": "pending"}).json()[0]["id"]
    rejected = client.post(
        f"/api/v1/actions/{action_id}/reject",
        json={"actorId": "operator", "reason": "入口仍有车辆，暂缓封闭"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    duplicate = client.post(
        f"/api/v1/actions/{action_id}/confirm",
        json={"actorId": "operator", "reason": "重复操作"},
    )
    assert duplicate.status_code == 409


def test_edge_telemetry_is_idempotent_and_generates_forecast(client):
    envelope = {
        "eventId": "edge-event-water-0001",
        "schemaVersion": 1,
        "eventType": "water.state",
        "tenantId": "demo-tenant",
        "siteId": "site-binh-rd-tunnel",
        "stationId": "station-binh-rd-tunnel",
        "deviceId": "dev-binh-rd-tunnel-camera",
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "sequenceNo": 90001,
        "traceId": "edge-trace-0001",
        "refs": {
            "demVersion": "dem-bh-20260701-v17",
            "calibrationVersion": "cal-bh-v9",
            "modelVersion": "reflection-v0.4.2",
        },
        "quality": {"score": 93, "status": "accepted", "flags": []},
        "payload": {
            "avgDepthCm": 15.4,
            "maxDepthCm": 25.1,
            "areaM2": 344.0,
            "volumeM3": 52.98,
            "depthSegmentsCm": [8.1, 16.8, 25.1, 19.0, 10.2],
            "slope1mCmMin": 0.72,
            "slope5mCmMin": 0.64,
            "slope10mCmMin": 0.58,
            "drainageSaturation": "red",
            "boundaryGeojson": {"type": "Polygon", "coordinates": []},
        },
    }
    accepted = client.post("/api/v1/edge/v1/telemetry", json=envelope)
    assert accepted.status_code == 202
    assert accepted.json()["accepted"] is True
    assert accepted.json()["duplicate"] is False
    assert accepted.json()["forecastRunId"]

    replay = client.post("/api/v1/edge/v1/telemetry", json=envelope)
    assert replay.status_code == 202
    assert replay.json()["duplicate"] is True

    latest = client.get("/api/v1/sites/site-binh-rd-tunnel")
    assert latest.json()["latestWater"]["maxDepthCm"] == 25.1
