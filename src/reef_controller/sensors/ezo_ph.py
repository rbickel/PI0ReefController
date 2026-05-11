"""Atlas Scientific EZO-pH driver."""
from __future__ import annotations

from typing import Iterable

from .base import Reading, Sensor
from .ezo import DELAY_CALIBRATE, EzoDevice, EzoError, SMBusTransport
from .registry import register_sensor


@register_sensor
class EzoPhSensor(Sensor):
    """Atlas Scientific EZO-pH circuit (I²C, default address 0x63).

    Options:
        address:        I²C address (default 0x63)
        bus:            I²C bus number (default 1)
        temperature_c:  static temperature compensation value (°C). Optional.
                        If omitted, the chip uses its last-set value (default 25 °C).
        unit:           reported unit (default "pH")

    Reads a single pH value (0.001 precision per datasheet).
    """

    type_name = "ezo_ph"
    DEFAULT_ADDRESS = 0x63

    def __init__(self, sensor_id: str, interval: float, options: dict | None = None) -> None:
        super().__init__(sensor_id, interval, options)
        self._address = int(self.options.get("address", self.DEFAULT_ADDRESS))
        self._bus_number = int(self.options.get("bus", 1))
        self._temperature_c = self.options.get("temperature_c")
        self._unit = str(self.options.get("unit", "pH"))
        # Allow tests to inject a transport.
        transport = self.options.get("_transport")
        if transport is None:
            transport = SMBusTransport(self._bus_number)
        self._device = EzoDevice(self._address, transport)

    def read(self) -> Iterable[Reading]:
        if self._temperature_c is not None:
            self._device.set_temperature_compensation(float(self._temperature_c))
        raw = self._device.read_value()
        try:
            value = float(raw)
        except ValueError as exc:
            raise EzoError(f"EZO-pH @0x{self._address:02x}: unparseable {raw!r}") from exc
        return [Reading.now(self.id, round(value, 3), self._unit, "ezo_ph")]

    # --- calibration helpers used by the CLI ----------------------------------

    def calibrate(self, point: str, value: float) -> str:
        """Run a calibration command.

        :param point: one of ``"mid"``, ``"low"``, ``"high"``.
        :param value: buffer pH value, e.g. 7.00, 4.00, 10.00.
        :returns: the new ``Cal,?`` status string.
        """
        if point not in {"mid", "low", "high"}:
            raise ValueError(f"unknown pH calibration point: {point!r}")
        self._device.command(f"Cal,{point},{value:.2f}", delay=DELAY_CALIBRATE)
        return self._device.calibration_status()

    def calibration_status(self) -> str:
        return self._device.calibration_status()

    def clear_calibration(self) -> None:
        self._device.clear_calibration()

    @property
    def device(self) -> EzoDevice:
        return self._device
