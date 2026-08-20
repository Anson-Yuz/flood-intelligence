from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from yujian_edge.config import ConfigError, EdgeConfig
from yujian_edge.envelope import (
    DEM_METADATA,
    EDGE_HEARTBEAT,
    WATER_BOUNDARY,
    WATER_STATE,
    EnvelopeFactory,
    mqtt_topic,
)
from yujian_edge.outbox import SQLiteOutbox
from yujian_edge.runtime import EdgeRuntime
from yujian_edge.transports import HttpTransport, TransportError


def config_mapping(sqlite_path: str, mode: str = "stdout") -> dict[str, Any]:
    return {
        "configVersion": "test-v1",
        "identity": {
            "tenantId": "tenant-a",
            "siteId": "site-a",
            "stationId": "station-a",
            "pointId": "point-a",
            "edgeNodeId": "edge-a",
        },
        "transport": {"mode": mode},
        "queue": {
            "sqlitePath": sqlite_path,
            "batchSize": 20,
            "retryBaseSeconds": 0.01,
            "retryMaxSeconds": 0.1,
        },
        "runtime": {},
        "adapters": {
            "lidar": {"driver": "mock", "options": {}},
            "camera": {"driver": "mock", "options": {}},
        },
    }


class RecordingTransport:
    def __init__(self) -> None:
        self.events: list[tuple[str, Mapping[str, Any]]] = []

    def send(self, envelope: Mapping[str, Any], topic: str) -> None:
        self.events.append((topic, envelope))

    def close(self) -> None:
        return None


class FailingTransport:
    def send(self, envelope: Mapping[str, Any], topic: str) -> None:
        raise TransportError("simulated offline link")

    def close(self) -> None:
        return None


class EdgeTests(unittest.TestCase):
    def test_config_rejects_missing_http_endpoint(self) -> None:
        data = config_mapping("queue.db", mode="http")
        data["transport"] = {"mode": "http", "http": {}}
        with self.assertRaises(ConfigError):
            EdgeConfig.from_mapping(data)

    def test_envelope_contract_and_topic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = EdgeConfig.from_mapping(config_mapping(str(Path(directory) / "queue.db")))
            outbox = SQLiteOutbox(config.queue.sqlite_path)
            event = EnvelopeFactory(config, outbox.next_sequence).create(
                WATER_STATE,
                {"maxDepthCm": 12.4},
            ).to_dict()
            self.assertEqual(event["schemaVersion"], "yujian.edge.event/v1")
            self.assertEqual(event["sequence"], 1)
            self.assertEqual(event["subject"]["stationId"], "station-a")
            self.assertEqual(
                mqtt_topic(event),
                "yujian/v1/tenant-a/site-a/station-a/events/water.state.v1",
            )

    def test_offline_event_is_persisted_then_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = EdgeConfig.from_mapping(config_mapping(str(Path(directory) / "queue.db")))
            outbox = SQLiteOutbox(
                config.queue.sqlite_path,
                retry_base_seconds=0.01,
                retry_max_seconds=0.1,
            )
            event = EnvelopeFactory(config, outbox.next_sequence).create(
                EDGE_HEARTBEAT,
                {"status": "online"},
            ).to_dict()
            outbox.enqueue(event)
            failed = outbox.flush(FailingTransport(), force=True)
            self.assertEqual(failed.failed, 1)
            self.assertEqual(outbox.pending_count(), 1)

            recording = RecordingTransport()
            recovered = outbox.flush(recording, force=True)
            self.assertEqual(recovered.delivered, 1)
            self.assertEqual(recovered.remaining, 0)
            self.assertEqual(recording.events[0][1]["eventId"], event["eventId"])

    def test_runtime_emits_all_required_event_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = EdgeConfig.from_mapping(config_mapping(str(Path(directory) / "queue.db")))
            recording = RecordingTransport()
            runtime = EdgeRuntime(config, transport=recording)
            try:
                result = runtime.run_once()
            finally:
                runtime.close()
            self.assertEqual(result.remaining, 0)
            event_types = {event["eventType"] for _, event in recording.events}
            self.assertEqual(
                event_types,
                {DEM_METADATA, WATER_STATE, WATER_BOUNDARY, EDGE_HEARTBEAT},
            )
            water_events = [event for _, event in recording.events if event["eventType"].startswith("water.")]
            self.assertEqual(len({event["traceId"] for event in water_events}), 1)


class HttpTransportTests(unittest.TestCase):
    def test_http_transport_posts_the_same_envelope(self) -> None:
        received: list[dict[str, Any]] = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers["Content-Length"])
                received.append(json.loads(self.rfile.read(length)))
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"accepted":true}')

            def log_message(self, _format: str, *args: object) -> None:
                return None

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            envelope = {
                "eventId": "event-1",
                "eventType": EDGE_HEARTBEAT,
                "source": {"tenantId": "tenant-a"},
                "subject": {"siteId": "site-a", "stationId": "station-a"},
            }
            transport = HttpTransport(f"http://127.0.0.1:{server.server_port}/events")
            transport.send(envelope, "yujian/v1/test")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(received, [envelope])


if __name__ == "__main__":
    unittest.main()
