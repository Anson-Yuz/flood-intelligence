#!/usr/bin/env python3
"""Tiny local HTTP receiver for adapter integration demos."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        event = json.loads(self.rfile.read(length))
        print(
            json.dumps(
                {
                    "path": self.path,
                    "eventId": event.get("eventId"),
                    "eventType": event.get("eventType"),
                    "sequence": event.get("sequence"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        body = json.dumps({"accepted": True, "eventId": event.get("eventId")}).encode()
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args: object) -> None:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mock receiver listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
