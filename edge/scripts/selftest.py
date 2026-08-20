#!/usr/bin/env python3
"""Small dependency-free offline/replay smoke test."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yujian_edge.envelope import EDGE_HEARTBEAT  # noqa: E402
from yujian_edge.outbox import SQLiteOutbox  # noqa: E402
from yujian_edge.transports import TransportError  # noqa: E402


class Offline:
    def send(self, _envelope: Mapping[str, Any], _topic: str) -> None:
        raise TransportError("offline as requested by self-test")

    def close(self) -> None:
        return None


class Online:
    def __init__(self) -> None:
        self.received: list[Mapping[str, Any]] = []

    def send(self, envelope: Mapping[str, Any], _topic: str) -> None:
        self.received.append(envelope)

    def close(self) -> None:
        return None


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        queue = SQLiteOutbox(Path(directory) / "selftest.db", retry_base_seconds=0.01)
        event = {
            "schemaVersion": "yujian.edge.event/v1",
            "eventId": "selftest-event-1",
            "eventType": EDGE_HEARTBEAT,
            "source": {"tenantId": "selftest"},
            "subject": {"siteId": "site", "stationId": "station"},
            "payload": {"status": "online"},
        }
        queue.enqueue(event)
        offline = queue.flush(Offline(), force=True)
        assert offline.failed == 1 and offline.remaining == 1
        online = Online()
        replay = queue.flush(online, force=True)
        assert replay.delivered == 1 and replay.remaining == 0
        assert online.received[0]["eventId"] == "selftest-event-1"
    print("SELFTEST PASS: offline event persisted and replayed exactly once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
