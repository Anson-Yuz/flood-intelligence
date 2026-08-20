from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.database import Database


def test_create_schema_adds_auth_fields_to_legacy_users_table(tmp_path):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    legacy_engine = create_engine(database_url)
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    tenant_id VARCHAR(64) NOT NULL,
                    username VARCHAR(80) NOT NULL,
                    display_name VARCHAR(120) NOT NULL,
                    role VARCHAR(40) NOT NULL,
                    region_scope JSON NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_user_tenant_username UNIQUE (tenant_id, username)
                )
                """
            )
        )
    legacy_engine.dispose()

    database = Database(database_url)
    database.create_schema()
    inspector = inspect(database.engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    assert {"password_hash", "salt", "iterations"}.issubset(user_columns)
    assert "auth_sessions" in inspector.get_table_names()

    database.dispose()
