from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from sqlalchemy import select

from app.auth import hash_session_token
from app.config import Settings
from app.main import create_app
from app.models import ActionRecord, AuthSession, User


LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"


def _login(client, *, remember: bool = False):
    return client.post(
        LOGIN_URL,
        json={"username": "admin", "password": "Yujian@2026", "remember": remember},
    )


def test_login_rejects_wrong_password(client):
    response = client.post(
        LOGIN_URL,
        json={"username": "admin", "password": "wrong-password", "remember": False},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "用户名或密码错误"}


def test_login_me_and_logout(client):
    login = _login(client)
    assert login.status_code == 200
    body = login.json()
    assert body["ok"] is True
    assert body["authenticated"] is True
    assert body["remember"] is False
    assert body["user"] == {
        "id": body["user"]["id"],
        "username": "admin",
        "displayName": "王海峰",
        "role": "防汛值班长",
        "tenantId": "demo-tenant",
    }
    assert "yujian_session" in login.cookies
    assert "Max-Age=43200" in login.headers["set-cookie"]

    me = client.get(ME_URL)
    assert me.status_code == 200
    assert me.json()["user"]["displayName"] == "王海峰"

    logout = client.post(LOGOUT_URL)
    assert logout.status_code == 200
    assert logout.json() == {"ok": True, "authenticated": False}
    after_logout = client.get(ME_URL)
    assert after_logout.status_code == 401
    assert after_logout.json()["detail"] in {"未登录", "会话已过期或已注销"}


def test_expired_session_is_rejected(client):
    login = _login(client)
    token = login.cookies["yujian_session"]
    database = client.app.state.database
    with database.session_factory() as db:
        session = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
        assert session is not None
        session.expires_at = session.created_at - timedelta(seconds=1)
        db.commit()

    response = client.get(ME_URL)
    assert response.status_code == 401
    assert response.json() == {"detail": "会话已过期或已注销"}


def test_remember_session_has_extended_lifetime(client):
    response = _login(client, remember=True)
    assert response.status_code == 200
    assert response.json()["remember"] is True
    assert "Max-Age" in response.headers["set-cookie"]

    database = client.app.state.database
    token = response.cookies["yujian_session"]
    with database.session_factory() as db:
        session = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
        assert session is not None
        assert session.remember is True
        assert session.expires_at - session.created_at >= timedelta(days=29)


def test_ui_operator_prefers_authenticated_display_name(client):
    assert _login(client).status_code == 200
    response = client.post(
        "/api/v1/events/YJ-20260710-0148/manual-review",
        json={"operator": "请求体中的名字", "reason": "认证用户优先测试"},
    )
    assert response.status_code == 200
    assert response.json()["operator"] == "王海峰"

    database = client.app.state.database
    with database.session_factory() as db:
        action = db.get(ActionRecord, "action-bh-gate-001")
        assert action is not None
        assert action.decided_by == "王海峰"


def test_production_does_not_seed_known_local_default_password(tmp_path: Path):
    settings = Settings(
        environment="production",
        database_url=f"sqlite+pysqlite:///{(tmp_path / 'production.db').as_posix()}",
        seed_demo_data=False,
        auth_seed_admin_password="Yujian@2026",
        scenario_tick_seconds=3600,
        cors_origins=["http://localhost:5173"],
    )
    app = create_app(settings)
    with TestClient(app) as production_client:
        with production_client.app.state.database.session_factory() as db:
            admin = db.scalar(select(User).where(User.username == "admin"))
            assert admin is None
        response = production_client.post(
            LOGIN_URL,
            json={"username": "admin", "password": "Yujian@2026", "remember": False},
        )
        assert response.status_code == 401
