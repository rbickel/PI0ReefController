"""Atlas Scientific EZO chip support over I²C.

This module covers the protocol common to all EZO devices (pH, ORP, EC, RTD,
DO). Per-probe behaviour (output parsing, calibration commands) is in
:mod:`reef_controller.sensors.ezo_ph` and :mod:`reef_controller.sensors.ezo_ec`.

Protocol summary (Atlas EZO datasheets):

* I²C address: 0x61–0x6F (default depends on probe — pH 0x63, ORP 0x62,
  EC 0x64, RTD 0x66, DO 0x61).
* Write: ASCII command bytes, no terminator. Examples: ``R``, ``Cal,mid,7.00``.
* After the write, the chip processes the command for a known delay (e.g.
  900 ms for ``R``, 300 ms for most others, 1500 ms for ``Cal``).
* Read: up to 32 bytes. The first byte is a **status byte**:
    1   success
    2   syntax error
    254 still processing — wait and retry
    255 no data
  The remainder is the ASCII response, null-terminated and padded.

We deliberately keep the transport abstract so unit tests can run anywhere.
"""
from __future__ import annotations

import logging
import time
from typing import Protocol

log = logging.getLogger(__name__)


# --- Status bytes from the EZO datasheet ----------------------------------
STATUS_OK = 1
STATUS_SYNTAX_ERROR = 2
STATUS_PENDING = 254
STATUS_NO_DATA = 255

# --- Per-command processing delays (seconds) ------------------------------
DELAY_READ = 0.9          # 'R'
DELAY_CALIBRATE = 1.6     # 'Cal,*'
DELAY_DEFAULT = 0.3       # most other commands


class EzoError(IOError):
    """Raised when an EZO command does not succeed."""


class EzoTransport(Protocol):
    """Minimal I²C transport interface used by :class:`EzoDevice`.

    The production implementation wraps ``smbus2.SMBus``. Tests inject a
    fake transport that records writes and returns scripted replies.
    """

    def write(self, address: int, data: bytes) -> None: ...
    def read(self, address: int, length: int) -> bytes: ...


class SMBusTransport:
    """``smbus2``-backed transport.

    Imported lazily so the package works on Windows / CI where ``smbus2``
    is not installable.
    """

    def __init__(self, bus_number: int = 1) -> None:
        import smbus2  # noqa: WPS433 — intentional lazy import

        self._bus = smbus2.SMBus(bus_number)

    def write(self, address: int, data: bytes) -> None:
        # SMBus block writes are limited; use raw I²C transactions.
        import smbus2  # noqa: WPS433

        msg = smbus2.i2c_msg.write(address, list(data))
        self._bus.i2c_rdwr(msg)

    def read(self, address: int, length: int) -> bytes:
        import smbus2  # noqa: WPS433

        msg = smbus2.i2c_msg.read(address, length)
        self._bus.i2c_rdwr(msg)
        return bytes(msg)

    def close(self) -> None:
        self._bus.close()


class EzoDevice:
    """Thin wrapper around an EZO chip on a given I²C address.

    Use as a context manager when you want to ensure the transport is closed:

        with EzoDevice(0x63, SMBusTransport()) as ezo:
            print(ezo.info())
    """

    READ_BUFFER_LEN = 40    # 1 status byte + up to 39 ASCII

    def __init__(self, address: int, transport: EzoTransport) -> None:
        self.address = address
        self._t = transport

    # ----- low-level ------------------------------------------------------

    def command(self, cmd: str, *, delay: float = DELAY_DEFAULT,
                expect_response: bool = True, retries: int = 2) -> str:
        """Send a command, wait, and return the ASCII response.

        Raises :class:`EzoError` on syntax error or persistent pending state.
        Returns the response without the leading echo (some firmwares echo
        the command, prefixed with ``?``) and without trailing nulls.
        """
        payload = cmd.encode("ascii")
        log.debug("EZO @0x%02x → %s", self.address, cmd)
        self._t.write(self.address, payload)
        time.sleep(delay)

        if not expect_response:
            return ""

        for attempt in range(retries + 1):
            raw = self._t.read(self.address, self.READ_BUFFER_LEN)
            if not raw:
                raise EzoError(f"EZO @0x{self.address:02x}: empty read")
            status, body = raw[0], raw[1:]
            if status == STATUS_OK:
                text = body.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
                log.debug("EZO @0x%02x ← %s", self.address, text)
                return text
            if status == STATUS_PENDING:
                time.sleep(0.2)
                continue
            if status == STATUS_NO_DATA:
                return ""
            if status == STATUS_SYNTAX_ERROR:
                raise EzoError(
                    f"EZO @0x{self.address:02x}: syntax error for {cmd!r}"
                )
            raise EzoError(
                f"EZO @0x{self.address:02x}: unknown status byte {status}"
            )
        raise EzoError(
            f"EZO @0x{self.address:02x}: still pending after {retries + 1} reads"
        )

    # ----- common commands ------------------------------------------------

    def info(self) -> str:
        """Return ``i`` response, e.g. ``?I,pH,2.10``."""
        return self.command("i")

    def status(self) -> str:
        """Return ``Status`` response, e.g. ``?Status,P,5.038``."""
        return self.command("Status")

    def calibration_status(self) -> str:
        """Return ``Cal,?`` response, e.g. ``?Cal,2`` (2 = mid+low calibrated)."""
        return self.command("Cal,?")

    def clear_calibration(self) -> None:
        self.command("Cal,clear", delay=DELAY_CALIBRATE)

    def read_value(self) -> str:
        """Send the ``R`` (read) command and return the raw response string.

        Subclasses parse this differently (pH → single float, EC → CSV).
        """
        return self.command("R", delay=DELAY_READ)

    def set_temperature_compensation(self, temperature_c: float) -> None:
        """Send a ``T,<value>`` temperature-compensation update."""
        self.command(f"T,{temperature_c:.2f}")

    def sleep(self) -> None:
        """Put the chip to low-power sleep until the next command wakes it."""
        self.command("Sleep", expect_response=False)
