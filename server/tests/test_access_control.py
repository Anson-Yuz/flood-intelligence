from __future__ import annotations

from datetime import datetime, timezone

import pytest
from starlette.websockets import WebSocketDisconnect


def test_anonymous_operator_and_ui_rest_require_session(anonymous_client):
    for path in ("/api/v1/dashboard", "/api/v1/sites", "/api/snapshot"):
        response = anonymous_client.get(path)
        assert response.status_code == 401
        assert response.json() == {"detail": "未登录"}


def test_health_and_auth_login_are_public(anonymous_client):
    health = anonymous_client.get("/api/v1/health")
    assert health.status_code == 200
    session = anonymous_client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is False
    login = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Yujian@2026", "remember": False},
    )
    assert login.status_code == 200


def test_edge_heartbeat_ingest_is_public(anonymous_client):
    response = anonymous_client.post(
        "/api/v1/edge/v1/heartbeat",
        json={
            "stationId": "station-binh-rd-tunnel",
            "deviceId": "dev-binh-rd-tunnel-camera",
            "siteId": "site-binh-rd-tunnel",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "status": "online",
            "telemetry": {"source": "anonymous-edge-regression"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] is True


def test_anonymous_websocket_closes_4401_before_accept(anonymous_client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with anonymous_client.websocket_connect("/api/v1/ws/live"):
            pass
    assert exc_info.value.code == 4401
