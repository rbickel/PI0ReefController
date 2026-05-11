"""Thin wrapper around paho-mqtt with LWT + per-sensor availability tracking."""
from __future__ import annotations

import json
import logging
import threading
from typing import Optional

import paho.mqtt.client as mqtt

from .config import MqttConfig
from .sensors import Reading

log = logging.getLogger(__name__)

BRIDGE_AVAILABILITY_SUFFIX = "bridge/status"
ONLINE = "online"
OFFLINE = "offline"


class MqttClient:
    """MQTT publisher with reconnect + retained availability topics."""

    def __init__(self, cfg: MqttConfig) -> None:
        self._cfg = cfg
        self._bridge_topic = f"{cfg.base_topic}/{BRIDGE_AVAILABILITY_SUFFIX}"
        self._connected = threading.Event()
        self._availability: dict[str, str] = {}

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=cfg.client_id,
            clean_session=True,
        )
        if cfg.username:
            self._client.username_pw_set(cfg.username, cfg.password or "")
        if cfg.tls:
            self._client.tls_set()
        self._client.will_set(self._bridge_topic, OFFLINE, qos=1, retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        # Built-in reconnect with backoff.
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        log.info("Connecting to MQTT broker %s:%s", self._cfg.host, self._cfg.port)
        self._client.connect_async(self._cfg.host, self._cfg.port, keepalive=self._cfg.keepalive)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self._client.publish(self._bridge_topic, OFFLINE, qos=1, retain=True).wait_for_publish(timeout=2)
        except Exception:  # pragma: no cover - best-effort
            pass
        self._client.loop_stop()
        self._client.disconnect()

    # --- callbacks -------------------------------------------------------

    def _on_connect(self, client, _userdata, _flags, reason_code, _props=None):
        if reason_code == 0:
            log.info("MQTT connected")
            self._connected.set()
            client.publish(self._bridge_topic, ONLINE, qos=1, retain=True)
            # Re-assert known per-sensor availability after reconnects.
            for sid, state in self._availability.items():
                client.publish(self._availability_topic(sid), state, qos=1, retain=True)
        else:
            log.error("MQTT connect failed: %s", reason_code)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _props=None):
        self._connected.clear()
        log.warning("MQTT disconnected: %s", reason_code)

    # --- helpers ---------------------------------------------------------

    def _state_topic(self, sensor_id: str) -> str:
        return f"{self._cfg.base_topic}/{sensor_id}/state"

    def _availability_topic(self, sensor_id: str) -> str:
        return f"{self._cfg.base_topic}/{sensor_id}/availability"

    # --- public API ------------------------------------------------------

    def publish_reading(self, reading: Reading) -> None:
        topic = self._state_topic(reading.sensor_id)
        payload = json.dumps(reading.to_payload(), separators=(",", ":"))
        self._client.publish(topic, payload, qos=1, retain=True)
        log.debug("→ %s %s", topic, payload)

    def set_availability(self, sensor_id: str, online: bool) -> None:
        state = ONLINE if online else OFFLINE
        if self._availability.get(sensor_id) == state:
            return
        self._availability[sensor_id] = state
        self._client.publish(self._availability_topic(sensor_id), state, qos=1, retain=True)
        log.info("availability[%s] = %s", sensor_id, state)

    def wait_until_connected(self, timeout: Optional[float] = None) -> bool:
        return self._connected.wait(timeout=timeout)
