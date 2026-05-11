"""Atlas Scientific EZO-EC (conductivity) driver.

The EZO-EC chip outputs up to four comma-separated values per ``R`` command:
``EC,TDS,SAL,SG``. Which fields are enabled is set via the ``O,*`` commands.
This driver normalises the response and surfaces a single user-selected
quantity (salinity in PSU by default, which is what reef-tank monitoring
cares about).

Default I²C address: 0x64.
"""
from __future__ import annotations

from typing import Iterable

from .base import Reading, Sensor
from .ezo import DELAY_CALIBRATE, EzoDevice, EzoError, SMBusTransport
from .registry import register_sensor

# Output fields in the order the EZO-EC reports them when all are enabled.
_FIELD_ORDER = ("ec", "tds", "salinity", "sg")
_UNITS = {
    "ec": "µS/cm",
    "tds": "ppm",
    "salinity": "PSU",       # practical salinity units ≈ ppt for our purposes
    "sg": "",                # specific gravity is dimensionless
}


@register_sensor
class EzoEcSensor(Sensor):
    """Atlas Scientific EZO-EC circuit (I²C, default address 0x64).

    Options:
        address:        I²C address (default 0x64)
        bus:            I²C bus number (default 1)
        probe_k:        cell constant of the conductivity probe (e.g. 1.0)
                        — written once at startup; chip persists it.
        temperature_c:  static temperature compensation value (°C). Optional.
        output:         which field to publish — one of ``ec``, ``tds``,
                        ``salinity``, ``sg`` (default ``salinity``).
        unit:           override the unit string for the payload.

    Emits one :class:`~reef_controller.sensors.base.Reading`.
    """

    type_name = "ezo_ec"
    DEFAULT_ADDRESS = 0x64

    def __init__(self, sensor_id: str, interval: float, options: dict | None = None) -> None:
        super().__init__(sensor_id, interval, options)
        self._address = int(self.options.get("address", self.DEFAULT_ADDRESS))
        self._bus_number = int(self.options.get("bus", 1))
        self._temperature_c = self.options.get("temperature_c")
        self._output = str(self.options.get("output", "salinity")).lower()
        if self._output not in _FIELD_ORDER:
            raise ValueError(
                f"ezo_ec: unsupported output {self._output!r}; expected one of {_FIELD_ORDER}"
            )
        self._unit = str(self.options.get("unit", _UNITS[self._output]))
        self._probe_k = self.options.get("probe_k")

        transport = self.options.get("_transport")
        if transport is None:
            transport = SMBusTransport(self._bus_number)
        self._device = EzoDevice(self._address, transport)

        self._configured = False

    # ----- one-time chip config ----------------------------------------------

    def _ensure_configured(self) -> None:
        if self._configured:
            return
        # Make sure the four output fields are all enabled so we can index by
        # position regardless of the chip's previous config.
        for field in _FIELD_ORDER:
            tag = {"ec": "EC", "tds": "TDS", "salinity": "S", "sg": "SG"}[field]
            self._device.command(f"O,{tag},1")
        if self._probe_k is not None:
            self._device.command(f"K,{float(self._probe_k):.2f}")
        self._configured = True

    # ----- main read ---------------------------------------------------------

    def read(self) -> Iterable[Reading]:
        self._ensure_configured()
        if self._temperature_c is not None:
            self._device.set_temperature_compensation(float(self._temperature_c))
        raw = self._device.read_value()
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) != len(_FIELD_ORDER):
            raise EzoError(
                f"EZO-EC @0x{self._address:02x}: expected {len(_FIELD_ORDER)} fields, got {raw!r}"
            )
        try:
            values = {name: float(v) for name, v in zip(_FIELD_ORDER, parts)}
        except ValueError as exc:
            raise EzoError(f"EZO-EC @0x{self._address:02x}: unparseable {raw!r}") from exc
        value = round(values[self._output], 3)
        return [Reading.now(self.id, value, self._unit, "ezo_ec")]

    # ----- calibration helpers ------------------------------------------------

    def calibrate(self, point: str, value: float | None = None) -> str:
        """Run a calibration step.

        :param point: ``"dry"``, ``"low"``, ``"high"`` or ``"single"``.
        :param value: µS/cm value of the standard (required for low/high/single).
        :returns: the new ``Cal,?`` status string.
        """
        self._ensure_configured()
        if point == "dry":
            cmd = "Cal,dry"
        elif point in {"low", "high", "single"}:
            if value is None:
                raise ValueError(f"ezo_ec: {point!r} calibration needs a value (µS/cm)")
            cmd = f"Cal,{point},{int(value)}"
        else:
            raise ValueError(f"unknown EC calibration point: {point!r}")
        self._device.command(cmd, delay=DELAY_CALIBRATE)
        return self._device.calibration_status()

    def set_probe_k(self, k: float) -> None:
        self._ensure_configured()
        self._device.command(f"K,{float(k):.2f}")

    def calibration_status(self) -> str:
        return self._device.calibration_status()

    def clear_calibration(self) -> None:
        self._device.clear_calibration()

    @property
    def device(self) -> EzoDevice:
        return self._device
