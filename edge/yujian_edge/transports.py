from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any, Mapping, Protocol

from .envelope import canonical_json


class TransportError(RuntimeError):
    """A retryable outbound transport failure."""


class EventTransport(Protocol):
    def send(self, envelope: Mapping[str, Any], topic: str) -> None: ...

    def close(self) -> None: ...


class StdoutTransport:
    def send(self, envelope: Mapping[str, Any], topic: str) -> None:
        print(json.dumps({"topic": topic, "event": envelope}, ensure_ascii=False), flush=True)

    def close(self) -> None:
        return None


class HttpTransport:
    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: float = 5.0,
        headers: Mapping[str, str] | None = None,
        bearer_token_env: str | None = None,
    ):
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.headers = dict(headers or {})
        self.bearer_token_env = bearer_token_env

    def send(self, envelope: Mapping[str, Any], topic: str) -> None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Yujian-Event-Id": str(envelope["eventId"]),
            "X-Yujian-Event-Type": str(envelope["eventType"]),
            "X-Yujian-Mqtt-Topic": topic,
            **self.headers,
        }
        if self.bearer_token_env:
            token = os.getenv(self.bearer_token_env)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.endpoint,
            data=canonical_json(envelope).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                if not 200 <= response.status < 300:
                    raise TransportError(f"HTTP transport returned {response.status}")
                response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransportError(f"HTTP transport failed: {exc}") from exc

    def close(self) -> None:
        return None


class MqttTransport:
    """Optional MQTT QoS 1 transport.

    paho-mqtt is imported only when this transport is selected, so HTTP and
    stdout operation remain dependency-free.
    """

    def __init__(self, settings: Mapping[str, Any]):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise TransportError(
                "MQTT mode requires the optional dependency: pip install '.[mqtt]'"
            ) from exc
        self._mqtt = mqtt
        self._settings = dict(settings)
        self._client = mqtt.Client(
            client_id=str(settings.get("clientId", "yujian-edge")),
            clean_session=False,
            protocol=mqtt.MQTTv311,
        )
        username_env = settings.get("usernameEnv")
        password_env = settings.get("passwordEnv")
        username = os.getenv(str(username_env)) if username_env else None
        password = os.getenv(str(password_env)) if password_env else None
        if username:
            self._client.username_pw_set(username, password)
        if bool(settings.get("tls", False)):
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._connected = False

    def _connect(self) -> None:
        if self._connected:
            return
        try:
            self._client.connect(
                str(self._settings["host"]),
                int(self._settings.get("port", 8883 if self._settings.get("tls") else 1883)),
                int(self._settings.get("keepaliveSeconds", 60)),
            )
            self._client.loop_start()
            self._connected = True
        except (OSError, ValueError) as exc:
            raise TransportError(f"MQTT connection failed: {exc}") from exc

    def send(self, envelope: Mapping[str, Any], topic: str) -> None:
        self._connect()
        try:
            info = self._client.publish(
                topic,
                canonical_json(envelope),
                qos=int(self._settings.get("qos", 1)),
                retain=False,
            )
            if info.rc != self._mqtt.MQTT_ERR_SUCCESS:
                self._connected = False
                raise TransportError(f"MQTT publish rejected with rc={info.rc}")
            info.wait_for_publish(timeout=float(self._settings.get("publishTimeoutSeconds", 5)))
            if not info.is_published():
                self._connected = False
                raise TransportError("MQTT publish acknowledgement timed out")
        except (OSError, RuntimeError, ValueError) as exc:
            self._connected = False
            if isinstance(exc, TransportError):
                raise
            raise TransportError(f"MQTT publish failed: {exc}") from exc

    def close(self) -> None:
        if self._connected:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False


def build_transport(config: Mapping[str, Any]) -> EventTransport:
    mode = str(config.get("mode", "stdout")).lower()
    if mode == "stdout":
        return StdoutTransport()
    if mode == "http":
        settings = config["http"]
        return HttpTransport(
            str(settings["endpoint"]),
            timeout_seconds=float(settings.get("timeoutSeconds", 5)),
            headers=settings.get("headers", {}),
            bearer_token_env=settings.get("bearerTokenEnv"),
        )
    if mode == "mqtt":
        return MqttTransport(config["mqtt"])
    print(f"unsupported transport mode: {mode}", file=sys.stderr)
    raise ValueError(f"unsupported transport mode: {mode}")
