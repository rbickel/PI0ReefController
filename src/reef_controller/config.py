"""Configuration loading from YAML."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MqttConfig:
    host: str = "localhost"
    port: int = 1883
    username: str | None = None
    password: str | None = None
    client_id: str = "pi0-reef-controller"
    base_topic: str = "reef"
    keepalive: int = 30
    tls: bool = False


@dataclass
class SensorConfig:
    id: str
    type: str
    interval: float = 10.0
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    mqtt: MqttConfig
    sensors: list[SensorConfig]
    log_level: str = "INFO"
    failure_threshold: int = 3


_KNOWN_SENSOR_FIELDS = {"id", "type", "interval", "enabled"}


def load_config(path: str | Path) -> AppConfig:
    """Parse a YAML config file into an :class:`AppConfig`."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    mqtt_raw = raw.get("mqtt", {}) or {}
    mqtt = MqttConfig(**{k: v for k, v in mqtt_raw.items() if k in MqttConfig.__annotations__})

    sensors: list[SensorConfig] = []
    for entry in raw.get("sensors", []) or []:
        if "id" not in entry or "type" not in entry:
            raise ValueError(f"Sensor entry missing 'id' or 'type': {entry!r}")
        options = {k: v for k, v in entry.items() if k not in _KNOWN_SENSOR_FIELDS}
        sensors.append(
            SensorConfig(
                id=entry["id"],
                type=entry["type"],
                interval=float(entry.get("interval", 10.0)),
                enabled=bool(entry.get("enabled", True)),
                options=options,
            )
        )

    return AppConfig(
        mqtt=mqtt,
        sensors=sensors,
        log_level=(raw.get("logging") or {}).get("level", "INFO"),
        failure_threshold=int(raw.get("failure_threshold", 3)),
    )
