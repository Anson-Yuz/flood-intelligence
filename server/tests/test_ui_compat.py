from __future__ import annotations

from datetime import date


EVENT_ID = "YJ-20260710-0148"


def test_ui_snapshot_reuses_dashboard_summary(client):
    snapshot = client.get("/api/snapshot")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["ok"] is True
    assert payload["source"] == "server-persisted-demo"
    assert payload["overview"]["siteCount"] == 4
    assert payload["primarySite"]["id"] == "site-binh-rd-tunnel"
    assert len(payload["forecastCurve"]) == 6


def test_ui_evidence_is_derived_from_persisted_state(client):
    evidence = client.get(f"/api/events/{EVENT_ID}/evidence")
    assert evidence.status_code == 200
    payload = evidence.json()
    assert payload["ok"] is True
    assert payload["eventId"] == EVENT_ID
    assert payload["frameId"].startswith("FRAME-SITE-BINH-RD-TUNNEL-")
    assert payload["maximumDepth"] == 22.8
    assert payload["floodedArea"] == 318.0
    captured_on = date.fromisoformat(payload["capturedAt"][:10])
    assert payload["demAgeDays"] == (captured_on - date(2026, 7, 1)).days
    assert payload["forecastRunId"].startswith("fc-")
    assert len(payload["checksum"]) == 64


def test_ui_publish_confirms_existing_action_and_audits_receipts(client):
    before = client.get("/api/actions", params={"status": "pending"}).json()
    action_id = before[0]["id"]
    response = client.post(
        f"/api/events/{EVENT_ID}/publish",
        json={
            "operator": "王海峰",
            "channels": ["gate", "led", "app", "patrol"],
            "action": "关闭北口道闸并发布绕行提示",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert payload["actionId"] == action_id
    assert payload["actionStatus"] == "confirmed"
    assert payload["channels"] == ["gate", "led", "app", "patrol"]
    assert len(payload["receipts"]) == 4

    actions = client.get("/api/actions").json()
    action = next(item for item in actions if item["id"] == action_id)
    assert action["status"] == "confirmed"
    assert action["decidedBy"] == "王海峰"
    assert action["edgeResponse"]["uiPublication"]["receiptId"] == payload["receiptId"]

    audit = client.get("/api/audit", params={"action": "event.warning.published"}).json()
    assert audit[0]["resourceId"] == EVENT_ID
    assert audit[0]["detail"]["channels"] == ["gate", "led", "app", "patrol"]

    replay = client.post(
        f"/api/events/{EVENT_ID}/publish",
        json={"operator": "王海峰", "channels": ["gate"], "action": "重复发布"},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent"] is True
    assert replay.json()["receiptId"] == payload["receiptId"]


def test_ui_manual_review_rejects_existing_action_and_records_queue(client):
    action_id = client.get("/api/actions", params={"status": "pending"}).json()[0]["id"]
    response = client.post(
        f"/api/events/{EVENT_ID}/manual-review",
        json={"operator": "王海峰", "reason": "需要现场人员复核积水边界与道闸状态"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert payload["queue"] == "防汛人工复核队列"
    assert payload["actionId"] == action_id
    assert payload["actionStatus"] == "rejected"

    rejected = client.get("/api/actions", params={"status": "rejected"}).json()[0]
    assert rejected["id"] == action_id
    assert rejected["decisionReason"] == payload["reason"]
    assert rejected["edgeResponse"]["manualReview"]["queue"] == payload["queue"]

    alerts = client.get("/api/alerts", params={"site_id": "site-binh-rd-tunnel"}).json()
    main_alert = next(item for item in alerts if item["id"] == payload["alertId"])
    assert main_alert["status"] == "manual_review"

    audit = client.get("/api/audit", params={"action": "event.manual_review.queued"}).json()
    assert audit[0]["resourceId"] == EVENT_ID
    assert audit[0]["detail"]["actionId"] == action_id


def test_ui_compat_unknown_event_is_404(client):
    response = client.get("/api/events/YJ-UNKNOWN/evidence")
    assert response.status_code == 404
