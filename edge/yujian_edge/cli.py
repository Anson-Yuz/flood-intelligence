from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Sequence

from .config import ConfigError, EdgeConfig
from .runtime import EdgeRuntime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yujian-edge", description="Yujian Ubuntu edge collector")
    parser.add_argument("--config", default="config.example.json", help="path to JSON configuration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-config", help="validate configuration and exit")
    subparsers.add_parser("run", help="run the long-lived collector")
    once = subparsers.add_parser("once", help="collect DEM, water data, heartbeat, then flush")
    once.add_argument("--no-dem", action="store_true", help="skip DEM collection")
    subparsers.add_parser("heartbeat", help="queue and flush one heartbeat")
    subparsers.add_parser("sample", help="queue and flush water state plus boundary")
    subparsers.add_parser("dem", help="queue and flush DEM metadata")
    flush = subparsers.add_parser("flush", help="force retry of queued events")
    flush.add_argument("--json", action="store_true", help="print machine-readable result")
    subparsers.add_parser("queue-status", help="show durable outbox status")
    handle = subparsers.add_parser("handle-command", help="execute a safe command JSON file")
    handle.add_argument("command_file", help="path to command JSON")
    return parser


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = EdgeConfig.load(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    _configure_logging(config.runtime.log_level)
    if args.command == "validate-config":
        print(f"configuration valid: {Path(args.config).resolve()}")
        return 0

    runtime: EdgeRuntime | None = None
    try:
        runtime = EdgeRuntime(config)
        if args.command == "queue-status":
            print(json.dumps(runtime.outbox.status(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "flush":
            result = runtime.flush(force=True)
            output = {
                "attempted": result.attempted,
                "delivered": result.delivered,
                "failed": result.failed,
                "remaining": result.remaining,
            }
            print(json.dumps(output, ensure_ascii=False, indent=None if args.json else 2))
            return 0 if result.failed == 0 else 1

        runtime.connect()
        if args.command == "run":
            stop_event = threading.Event()

            def stop(_signum: int, _frame: object) -> None:
                stop_event.set()

            signal.signal(signal.SIGINT, stop)
            signal.signal(signal.SIGTERM, stop)
            runtime.run_forever(stop_event)
            return 0
        if args.command == "once":
            result = runtime.run_once(include_dem=not args.no_dem)
            return 0 if result.failed == 0 else 1
        if args.command == "heartbeat":
            runtime.emit_heartbeat()
        elif args.command == "sample":
            runtime.emit_water()
        elif args.command == "dem":
            runtime.emit_dem()
        elif args.command == "handle-command":
            with Path(args.command_file).open("r", encoding="utf-8") as handle:
                command = json.load(handle)
            ack = runtime.execute_command(command)
            print(json.dumps(ack, ensure_ascii=False, indent=2))
            return 0 if ack["payload"]["status"] == "succeeded" else 1
        result = runtime.flush(force=True)
        return 0 if result.failed == 0 else 1
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        logging.getLogger("yujian_edge").error("%s", exc)
        return 1
    finally:
        if runtime is not None:
            runtime.close()
