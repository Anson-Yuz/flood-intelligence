from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, database_url: str) -> None:
        engine_options: dict[str, object] = {
            "pool_pre_ping": True,
            "future": True,
        }
        if database_url.startswith("sqlite"):
            engine_options["connect_args"] = {"check_same_thread": False}

        self.engine: Engine = create_engine(database_url, **engine_options)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def create_schema(self) -> None:
        # Importing models ensures all mapped tables are registered.
        from . import models  # noqa: F401

        Base.metadata.create_all(self.engine)
        self._ensure_legacy_user_auth_columns()

    def _ensure_legacy_user_auth_columns(self) -> None:
        inspector = inspect(self.engine)
        if "users" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("users")}
        required_columns = {
            "password_hash": "VARCHAR(128)",
            "salt": "VARCHAR(64)",
            "iterations": "INTEGER",
        }
        missing = [(name, sql_type) for name, sql_type in required_columns.items() if name not in existing]
        if not missing:
            return
        with self.engine.begin() as connection:
            for name, sql_type in missing:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {sql_type}"))

    def dispose(self) -> None:
        self.engine.dispose()


def get_db(request: Request) -> Generator[Session, None, None]:
    database: Database = request.app.state.database
    session = database.session_factory()
    try:
        yield session
    finally:
        session.close()
