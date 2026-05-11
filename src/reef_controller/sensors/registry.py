"""Sensor type registry."""
from __future__ import annotations

from typing import Type

from ..config import SensorConfig
from .base import Sensor

_REGISTRY: dict[str, Type[Sensor]] = {}


def register_sensor(cls: Type[Sensor]) -> Type[Sensor]:
    """Class decorator to register a sensor driver by its ``type_name``."""
    name = getattr(cls, "type_name", None)
    if not name or name == "abstract":
        raise ValueError(f"{cls.__name__} must declare a non-abstract type_name")
    if name in _REGISTRY:
        raise ValueError(f"Sensor type {name!r} already registered")
    _REGISTRY[name] = cls
    return cls


def build_sensor(cfg: SensorConfig) -> Sensor:
    try:
        cls = _REGISTRY[cfg.type]
    except KeyError as exc:
        raise ValueError(
            f"Unknown sensor type {cfg.type!r}. Known: {sorted(_REGISTRY)}"
        ) from exc
    return cls(sensor_id=cfg.id, interval=cfg.interval, options=cfg.options)


# Import drivers so they self-register. Keep imports here to avoid
# import-time side effects when only the base classes are needed.
from . import mock  # noqa: E402,F401
from . import ds18b20  # noqa: E402,F401
