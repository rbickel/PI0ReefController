"""Mock sensor: emits plausible random values for development."""
from __future__ import annotations

import random
from typing import Iterable

from .base import Reading, Sensor
from .registry import register_sensor


@register_sensor
class MockSensor(Sensor):
    """A configurable mock probe.

    Options:
        unit:        unit string for the payload (default "°C")
        sensor_type: value reported as "sensor" in the payload (default "mock")
        min, max:    inclusive bounds of the uniform random value
        precision:   decimals to round to (default 2)
    """

    type_name = "mock"

    def __init__(self, sensor_id: str, interval: float, options: dict | None = None) -> None:
        super().__init__(sensor_id, interval, options)
        self._unit = str(self.options.get("unit", "°C"))
        self._sensor_type = str(self.options.get("sensor_type", "mock"))
        self._min = float(self.options.get("min", 24.0))
        self._max = float(self.options.get("max", 26.0))
        self._precision = int(self.options.get("precision", 2))
        if self._max < self._min:
            raise ValueError(f"mock sensor {sensor_id}: max < min")

    def read(self) -> Iterable[Reading]:
        value = round(random.uniform(self._min, self._max), self._precision)
        return [Reading.now(self.id, value, self._unit, self._sensor_type)]
