from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture()
def anonymous_client(tmp_path: Path):
    db_path = tmp_path / "test-yujian-anonymous.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{db_path.as_posix()}",
        seed_demo_data=True,
        scenario_tick_seconds=3600,
        cors_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test-yujian.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{db_path.as_posix()}",
        seed_demo_data=True,
        scenario_tick_seconds=3600,
        cors_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Yujian@2026", "remember": False},
        )
        assert login.status_code == 200, login.text
        yield test_client
