from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


class ConfigError(ValueError):
    """Raised when the edge configuration is incomplete or inconsistent."""


def _required_text(data: Mapping[str, Any], key: str, location: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{location}.{key} must be a non-empty string")
    return value.strip()


def _positive_number(data: Mapping[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"{key} must be greater than zero")
    return float(value)


@dataclass(frozen=True)
class IdentityConfig:
    tenant_id: str
    site_id: str
    station_id: str
    point_id: str
    edge_node_id: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "IdentityConfig":
        return cls(
            tenant_id=_required_text(data, "tenantId", "identity"),
            site_id=_required_text(data, "siteId", "identity"),
            station_id=_required_text(data, "stationId", "identity"),
            point_id=_required_text(data, "pointId", "identity"),
            edge_node_id=_required_text(data, "edgeNodeId", "identity"),
        )


@dataclass(frozen=True)
class QueueConfig:
    sqlite_path: Path
    batch_size: int = 50
    retry_base_seconds: float = 2.0
    retry_max_seconds: float = 300.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], base_dir: Path) -> "QueueConfig":
        raw_path = _required_text(data, "sqlitePath", "queue")
        sqlite_path = Path(raw_path).expanduser()
        if not sqlite_path.is_absolute():
            sqlite_path = (base_dir / sqlite_path).resolve()
        batch_size = int(_positive_number(data, "batchSize", 50))
        retry_base = _positive_number(data, "retryBaseSeconds", 2)
        retry_max = _positive_number(data, "retryMaxSeconds", 300)
        if retry_max < retry_base:
            raise ConfigError("queue.retryMaxSeconds must be >= retryBaseSeconds")
        return cls(sqlite_path, batch_size, retry_base, retry_max)


@dataclass(frozen=True)
class RuntimeConfig:
    mode: str = "rain_monitor"
    heartbeat_interval_seconds: float = 30.0
    observation_interval_seconds: float = 5.0
    dem_interval_seconds: float = 3600.0
    flush_interval_seconds: float = 2.0
    log_level: str = "INFO"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RuntimeConfig":
        return cls(
            mode=str(data.get("mode", "rain_monitor")),
            heartbeat_interval_seconds=_positive_number(data, "heartbeatIntervalSeconds", 30),
            observation_interval_seconds=_positive_number(data, "observationIntervalSeconds", 5),
            dem_interval_seconds=_positive_number(data, "demIntervalSeconds", 3600),
            flush_interval_seconds=_positive_number(data, "flushIntervalSeconds", 2),
            log_level=str(data.get("logLevel", "INFO")).upper(),
        )


@dataclass(frozen=True)
class AdapterConfig:
    driver: str
    class_path: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], location: str) -> "AdapterConfig":
        driver = _required_text(data, "driver", location).lower()
        class_path = data.get("classPath")
        if class_path is not None and not isinstance(class_path, str):
            raise ConfigError(f"{location}.classPath must be a string or null")
        options = data.get("options", {})
        if not isinstance(options, Mapping):
            raise ConfigError(f"{location}.options must be an object")
        if driver == "python" and not class_path:
            raise ConfigError(f"{location}.classPath is required when driver=python")
        if driver not in {"mock", "python"}:
            raise ConfigError(f"{location}.driver must be mock or python")
        return cls(driver, class_path, dict(options))


@dataclass(frozen=True)
class EdgeConfig:
    config_version: str
    identity: IdentityConfig
    transport: Mapping[str, Any]
    queue: QueueConfig
    runtime: RuntimeConfig
    lidar: AdapterConfig
    camera: AdapterConfig
    config_path: Path | None = None

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        base_dir: Path | None = None,
        config_path: Path | None = None,
    ) -> "EdgeConfig":
        base_dir = (base_dir or Path.cwd()).resolve()
        transport = data.get("transport")
        if not isinstance(transport, Mapping):
            raise ConfigError("transport must be an object")
        mode = str(transport.get("mode", "")).lower()
        if mode not in {"stdout", "http", "mqtt"}:
            raise ConfigError("transport.mode must be stdout, http, or mqtt")
        if mode == "http":
            http = transport.get("http")
            if not isinstance(http, Mapping):
                raise ConfigError("transport.http must be an object when mode=http")
            _required_text(http, "endpoint", "transport.http")
        if mode == "mqtt":
            mqtt = transport.get("mqtt")
            if not isinstance(mqtt, Mapping):
                raise ConfigError("transport.mqtt must be an object when mode=mqtt")
            _required_text(mqtt, "host", "transport.mqtt")

        queue_data = data.get("queue", {})
        runtime_data = data.get("runtime", {})
        adapters = data.get("adapters", {})
        if not isinstance(queue_data, Mapping) or not isinstance(runtime_data, Mapping):
            raise ConfigError("queue and runtime must be objects")
        if not isinstance(adapters, Mapping):
            raise ConfigError("adapters must be an object")
        lidar = adapters.get("lidar")
        camera = adapters.get("camera")
        if not isinstance(lidar, Mapping) or not isinstance(camera, Mapping):
            raise ConfigError("adapters.lidar and adapters.camera must be objects")

        identity = data.get("identity")
        if not isinstance(identity, Mapping):
            raise ConfigError("identity must be an object")
        return cls(
            config_version=_required_text(data, "configVersion", "root"),
            identity=IdentityConfig.from_mapping(identity),
            transport=dict(transport),
            queue=QueueConfig.from_mapping(queue_data, base_dir),
            runtime=RuntimeConfig.from_mapping(runtime_data),
            lidar=AdapterConfig.from_mapping(lidar, "adapters.lidar"),
            camera=AdapterConfig.from_mapping(camera, "adapters.camera"),
            config_path=config_path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "EdgeConfig":
        config_path = Path(path).expanduser().resolve()
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError as exc:
            raise ConfigError(f"configuration file not found: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid JSON in {config_path}: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ConfigError("configuration root must be an object")
        return cls.from_mapping(data, base_dir=config_path.parent, config_path=config_path)
