"""Sensor base class and Reading dataclass."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class Reading:
    """A single measurement emitted by a sensor."""
    sensor_id: str
    value: float
    unit: str
    sensor_type: str
    timestamp: datetime

    @staticmethod
    def now(sensor_id: str, value: float, unit: str, sensor_type: str) -> "Reading":
        return Reading(
            sensor_id=sensor_id,
            value=float(value),
            unit=unit,
            sensor_type=sensor_type,
            timestamp=datetime.now(timezone.utc),
        )

    def to_payload(self) -> dict:
        return {
            "value": self.value,
            "unit": self.unit,
            "sensor": self.sensor_type,
            "id": self.sensor_id,
            "ts": self.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


class Sensor(ABC):
    """Abstract sensor. Subclasses implement :meth:`read`."""

    #: Driver name registered with the sensor registry.
    type_name: str = "abstract"

    def __init__(self, sensor_id: str, interval: float, options: dict | None = None) -> None:
        self.id = sensor_id
        self.interval = float(interval)
        self.options = options or {}

    @abstractmethod
    def read(self) -> Iterable[Reading]:
        """Return one or more readings. Raise on transient failure."""

    def close(self) -> None:
        """Release any resources held by the driver."""
