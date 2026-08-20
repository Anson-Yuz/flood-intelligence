from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .config import EdgeConfig

SCHEMA_VERSION = "yujian.edge.event/v1"

EDGE_HEARTBEAT = "edge.heartbeat.v1"
WATER_STATE = "water.state.v1"
WATER_BOUNDARY = "water.boundary.v1"
DEM_METADATA = "road.dem.metadata.v1"
COMMAND_ACK = "edge.command.ack.v1"

EVENT_TYPES = {
    EDGE_HEARTBEAT,
    WATER_STATE,
    WATER_BOUNDARY,
    DEM_METADATA,
    COMMAND_ACK,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class EventEnvelope:
    schema_version: str
    event_id: str
    event_type: str
    occurred_at: str
    produced_at: str
    sequence: int
    trace_id: str
    source: Mapping[str, str]
    subject: Mapping[str, str]
    quality: Mapping[str, Any]
    context: Mapping[str, Any]
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "eventId": self.event_id,
            "eventType": self.event_type,
            "occurredAt": self.occurred_at,
            "producedAt": self.produced_at,
            "sequence": self.sequence,
            "traceId": self.trace_id,
            "source": dict(self.source),
            "subject": dict(self.subject),
            "quality": dict(self.quality),
            "context": dict(self.context),
            "payload": dict(self.payload),
        }


class EnvelopeFactory:
    def __init__(self, config: EdgeConfig, next_sequence: Callable[[], int]):
        self._config = config
        self._next_sequence = next_sequence

    def create(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        occurred_at: datetime | None = None,
        trace_id: str | None = None,
        quality: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> EventEnvelope:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type}")
        observed = occurred_at or utc_now()
        produced = utc_now()
        identity = self._config.identity
        return EventEnvelope(
            schema_version=SCHEMA_VERSION,
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            occurred_at=isoformat_z(observed),
            produced_at=isoformat_z(produced),
            sequence=self._next_sequence(),
            trace_id=trace_id or str(uuid.uuid4()),
            source={
                "tenantId": identity.tenant_id,
                "edgeNodeId": identity.edge_node_id,
            },
            subject={
                "siteId": identity.site_id,
                "stationId": identity.station_id,
                "pointId": identity.point_id,
            },
            quality=quality or {"status": "good", "confidence": 1.0, "reasons": []},
            context={"configVersion": self._config.config_version, **dict(context or {})},
            payload=dict(payload),
        )


_TOPIC_PART = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_topic_part(value: Any) -> str:
    return _TOPIC_PART.sub("_", str(value)).strip("_") or "unknown"


def mqtt_topic(envelope: Mapping[str, Any]) -> str:
    source = envelope["source"]
    subject = envelope["subject"]
    event_type = envelope["eventType"]
    return "/".join(
        [
            "yujian",
            "v1",
            _safe_topic_part(source["tenantId"]),
            _safe_topic_part(subject["siteId"]),
            _safe_topic_part(subject["stationId"]),
            "events",
            _safe_topic_part(event_type),
        ]
    )
