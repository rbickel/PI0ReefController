"""DS18B20 1-Wire temperature sensor driver.

Reads from the Linux 1-Wire kernel interface at /sys/bus/w1/devices/28-*/w1_slave.

Enable on Raspberry Pi OS by adding to /boot/firmware/config.txt:
    dtoverlay=w1-gpio
and ensuring the modules are loaded:
    sudo modprobe w1-gpio && sudo modprobe w1-therm

Each DS18B20 has a 64-bit ROM id; the device folder is "28-<12hex>".
The 'w1_slave' file content looks like:

    72 01 4b 46 7f ff 0e 10 57 : crc=57 YES
    72 01 4b 46 7f ff 0e 10 57 t=23125

The temperature is the integer after 't=', in millidegrees Celsius.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Iterable

from .base import Reading, Sensor
from .registry import register_sensor

_W1_BASE = "/sys/bus/w1/devices"


def _discover_serial() -> str | None:
    matches = glob.glob(os.path.join(_W1_BASE, "28-*"))
    if not matches:
        return None
    return Path(matches[0]).name


def _read_raw(serial: str) -> str:
    path = Path(_W1_BASE) / serial / "w1_slave"
    return path.read_text(encoding="ascii")


def parse_w1_slave(raw: str) -> float:
    """Parse the kernel 1-Wire output. Returns °C. Raises on malformed/CRC fail."""
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError("w1_slave: unexpected format")
    if not lines[0].endswith("YES"):
        raise IOError("w1_slave: CRC check failed")
    marker = "t="
    idx = lines[1].rfind(marker)
    if idx < 0:
        raise ValueError("w1_slave: missing 't=' field")
    milli = int(lines[1][idx + len(marker):])
    return milli / 1000.0


@register_sensor
class DS18B20Sensor(Sensor):
    """DS18B20 1-Wire temperature probe.

    Options:
        serial:    "28-xxxxxxxxxxxx" — if omitted, the first device found is used.
        unit:      "°C" (default) or "°F"
    """

    type_name = "ds18b20"

    def __init__(self, sensor_id: str, interval: float, options: dict | None = None) -> None:
        super().__init__(sensor_id, interval, options)
        self._serial: str | None = self.options.get("serial")
        self._unit = str(self.options.get("unit", "°C"))
        # Allow tests to inject a fake reader.
        self._reader = self.options.get("_reader", _read_raw)

    def _ensure_serial(self) -> str:
        if self._serial:
            return self._serial
        found = _discover_serial()
        if not found:
            raise FileNotFoundError(
                f"No DS18B20 found under {_W1_BASE}. Is the w1-gpio overlay enabled?"
            )
        self._serial = found
        return found

    def read(self) -> Iterable[Reading]:
        serial = self._ensure_serial()
        raw = self._reader(serial)
        celsius = parse_w1_slave(raw)
        value = celsius if self._unit == "°C" else celsius * 9 / 5 + 32
        return [Reading.now(self.id, round(value, 3), self._unit, "ds18b20")]
