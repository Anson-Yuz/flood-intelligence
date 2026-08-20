from __future__ import annotations

import logging
import platform
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from . import __version__
from .adapters import (
    CameraVendorAdapter,
    LidarVendorAdapter,
    build_camera_adapter,
    build_lidar_adapter,
)
from .config import EdgeConfig
from .envelope import (
    COMMAND_ACK,
    DEM_METADATA,
    EDGE_HEARTBEAT,
    WATER_BOUNDARY,
    WATER_STATE,
    EnvelopeFactory,
    isoformat_z,
    utc_now,
)
from .outbox import FlushResult, SQLiteOutbox
from .transports import EventTransport, build_transport

LOGGER = logging.getLogger("yujian_edge")
COMMAND_SCHEMA_VERSION = "yujian.edge.command/v1"


class EdgeRuntime:
    def __init__(
        self,
        config: EdgeConfig,
        *,
        transport: EventTransport | None = None,
        lidar: LidarVendorAdapter | None = None,
        camera: CameraVendorAdapter | None = None,
    ):
        self.config = config
        self.outbox = SQLiteOutbox(
            config.queue.sqlite_path,
            batch_size=config.queue.batch_size,
            retry_base_seconds=config.queue.retry_base_seconds,
            retry_max_seconds=config.queue.retry_max_seconds,
        )
        self.transport = transport or build_transport(config.transport)
        self.lidar = lidar or build_lidar_adapter(config.lidar)
        self.camera = camera or build_camera_adapter(config.camera)
        self.envelopes = EnvelopeFactory(config, self.outbox.next_sequence)
        self.started_at = time.monotonic()
        self.last_dem_version: str | None = None
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        self.lidar.connect()
        try:
            self.camera.connect()
        except Exception:
            self.lidar.close()
            raise
        self._connected = True

    def close(self) -> None:
        try:
            self.camera.close()
        finally:
            try:
                self.lidar.close()
            finally:
                self.transport.close()
                self._connected = False

    def _enqueue(self, envelope: Any) -> Mapping[str, Any]:
        event = envelope.to_dict()
        self.outbox.enqueue(event)
        return event

    def emit_heartbeat(self, *, trace_id: str | None = None) -> Mapping[str, Any]:
        observed = utc_now()
        payload = {
            "status": "online",
            "mode": self.config.runtime.mode,
            "uptimeSeconds": round(time.monotonic() - self.started_at, 3),
            "software": {
                "name": "yujian-edge",
                "version": __version__,
                "python": platform.python_version(),
                "os": platform.platform(),
            },
            "outbox": self.outbox.status(),
            "adapters": {
                "lidar": self.lidar.health().to_dict(),
                "camera": self.camera.health().to_dict(),
            },
            "clock": {"utc": isoformat_z(observed), "synchronized": None},
        }
        return self._enqueue(
            self.envelopes.create(
                EDGE_HEARTBEAT,
                payload,
                occurred_at=observed,
                trace_id=trace_id,
                context={"demVersion": self.last_dem_version},
            )
        )

    def emit_dem(self, *, trace_id: str | None = None) -> Mapping[str, Any]:
        observation = self.lidar.capture_dem_metadata()
        self.last_dem_version = observation.dem_version
        health = self.lidar.health()
        return self._enqueue(
            self.envelopes.create(
                DEM_METADATA,
                observation.payload(),
                occurred_at=observation.observed_at,
                trace_id=trace_id,
                quality={
                    "status": observation.quality_status,
                    "confidence": observation.confidence,
                    "reasons": list(observation.quality_reasons),
                },
                context={
                    "adapter": health.adapter,
                    "adapterVersion": health.adapter_version,
                    "calibrationVersion": observation.calibration_version,
                    "mock": bool(health.details.get("simulated", False)),
                },
            )
        )

    def emit_water(self, *, trace_id: str | None = None) -> list[Mapping[str, Any]]:
        observation = self.camera.capture_water_observation()
        trace_id = trace_id or str(uuid.uuid4())
        health = self.camera.health()
        common_context = {
            "adapter": health.adapter,
            "adapterVersion": health.adapter_version,
            "cameraCalibrationVersion": observation.calibration_version,
            "demVersion": self.last_dem_version,
            "mock": bool(health.details.get("simulated", False)),
        }
        quality = {
            "status": observation.quality_status,
            "confidence": observation.confidence,
            "reasons": list(observation.quality_reasons),
        }
        state = self._enqueue(
            self.envelopes.create(
                WATER_STATE,
                observation.state_payload(self.last_dem_version),
                occurred_at=observation.observed_at,
                trace_id=trace_id,
                quality=quality,
                context=common_context,
            )
        )
        boundary = self._enqueue(
            self.envelopes.create(
                WATER_BOUNDARY,
                observation.boundary_payload(self.last_dem_version),
                occurred_at=observation.observed_at,
                trace_id=trace_id,
                quality=quality,
                context=common_context,
            )
        )
        return [state, boundary]

    def flush(self, *, force: bool = False) -> FlushResult:
        result = self.outbox.flush(self.transport, force=force)
        if result.failed:
            LOGGER.warning(
                "outbox flush failed; queued events remain",
                extra={"remaining": result.remaining},
            )
        return result

    def run_once(self, *, include_dem: bool = True) -> FlushResult:
        self.connect()
        # Recover old events before adding the current observations.
        self.flush(force=True)
        if include_dem:
            self.emit_dem()
        self.emit_water()
        self.emit_heartbeat()
        return self.flush(force=True)

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        self.connect()
        self.flush(force=True)
        next_heartbeat = next_observation = next_dem = next_flush = 0.0
        while not stop_event.is_set():
            now = time.monotonic()
            try:
                if now >= next_dem:
                    self.emit_dem()
                    next_dem = now + self.config.runtime.dem_interval_seconds
                if now >= next_observation:
                    self.emit_water()
                    next_observation = now + self.config.runtime.observation_interval_seconds
                if now >= next_heartbeat:
                    self.emit_heartbeat()
                    next_heartbeat = now + self.config.runtime.heartbeat_interval_seconds
                if now >= next_flush:
                    self.flush()
                    next_flush = now + self.config.runtime.flush_interval_seconds
            except Exception:
                LOGGER.exception("edge collection cycle failed")
            stop_event.wait(0.2)
        self.flush(force=True)

    def execute_command(self, command: Mapping[str, Any]) -> Mapping[str, Any]:
        started = utc_now()
        command_id = str(command.get("commandId", "unknown"))
        command_type = str(command.get("commandType", "unknown"))
        trace_id = str(command.get("traceId") or command_id or uuid.uuid4())
        status = "succeeded"
        message = "command completed"
        try:
            self._validate_command(command)
            if command_type == "edge.collect.dem.v1":
                self.emit_dem(trace_id=trace_id)
            elif command_type == "edge.collect.water.v1":
                self.emit_water(trace_id=trace_id)
            elif command_type == "edge.heartbeat.v1":
                self.emit_heartbeat(trace_id=trace_id)
            elif command_type == "edge.flush.v1":
                self.flush(force=True)
            else:
                status = "rejected"
                message = "unsupported command type; actuator commands are intentionally disabled"
        except Exception as exc:
            status = "failed"
            message = str(exc)

        finished = utc_now()
        ack = self.envelopes.create(
            COMMAND_ACK,
            {
                "commandId": command_id,
                "commandType": command_type,
                "status": status,
                "message": message,
                "startedAt": isoformat_z(started),
                "finishedAt": isoformat_z(finished),
            },
            occurred_at=finished,
            trace_id=trace_id,
            quality={"status": "good", "confidence": 1.0, "reasons": []},
        )
        event = self._enqueue(ack)
        self.flush(force=True)
        return event

    def _validate_command(self, command: Mapping[str, Any]) -> None:
        if command.get("schemaVersion") != COMMAND_SCHEMA_VERSION:
            raise ValueError("unsupported command schemaVersion")
        if not command.get("commandId") or not command.get("commandType"):
            raise ValueError("commandId and commandType are required")
        target = command.get("target")
        if not isinstance(target, Mapping):
            raise ValueError("command target is required")
        identity = self.config.identity
        for key, expected in {
            "siteId": identity.site_id,
            "stationId": identity.station_id,
            "edgeNodeId": identity.edge_node_id,
        }.items():
            if target.get(key) != expected:
                raise ValueError(f"command target {key} does not match this edge node")
        expires_at = command.get("expiresAt")
        if expires_at:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                raise ValueError("expiresAt must include a timezone")
            if expiry.astimezone(timezone.utc) <= utc_now():
                raise ValueError("command has expired")
