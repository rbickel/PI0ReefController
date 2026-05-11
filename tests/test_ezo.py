"""Tests for the Atlas EZO drivers, using a fake I²C transport."""
from __future__ import annotations

from typing import Iterable

import pytest

from reef_controller.sensors.ezo import STATUS_OK, STATUS_PENDING, STATUS_SYNTAX_ERROR, EzoError
from reef_controller.sensors.ezo_ec import EzoEcSensor
from reef_controller.sensors.ezo_ph import EzoPhSensor


class FakeTransport:
    """Records writes, returns canned (status, body) responses in order."""

    def __init__(self, responses: Iterable[tuple[int, bytes]]) -> None:
        self.writes: list[tuple[int, bytes]] = []
        self._responses = list(responses)

    def write(self, address: int, data: bytes) -> None:
        self.writes.append((address, bytes(data)))

    def read(self, address: int, length: int) -> bytes:
        if not self._responses:
            raise AssertionError("FakeTransport: no more scripted responses")
        status, body = self._responses.pop(0)
        # Mimic the chip: pad with nulls up to `length`.
        payload = bytes([status]) + body + b"\x00" * (length - 1 - len(body))
        return payload[:length]


# ----- pH -----------------------------------------------------------------


def test_ezo_ph_reads_value_and_writes_temperature_compensation():
    transport = FakeTransport([
        (STATUS_OK, b""),               # response to "T,..."
        (STATUS_OK, b"7.213"),          # response to "R"
    ])
    sensor = EzoPhSensor(
        sensor_id="ph",
        interval=0,
        options={"_transport": transport, "temperature_c": 25.0},
    )
    readings = list(sensor.read())

    assert len(readings) == 1
    r = readings[0]
    assert r.value == pytest.approx(7.213)
    assert r.unit == "pH"
    assert r.sensor_type == "ezo_ph"
    # Temperature compensation was written before the read.
    assert transport.writes[0][1] == b"T,25.00"
    assert transport.writes[1][1] == b"R"


def test_ezo_ph_handles_pending_status_then_success():
    transport = FakeTransport([
        (STATUS_PENDING, b""),
        (STATUS_OK, b"8.04"),
    ])
    sensor = EzoPhSensor(
        sensor_id="ph",
        interval=0,
        options={"_transport": transport},   # no temp compensation
    )
    readings = list(sensor.read())
    assert readings[0].value == pytest.approx(8.04)


def test_ezo_ph_calibration_command_is_sent():
    transport = FakeTransport([
        (STATUS_OK, b""),         # response to "Cal,mid,7.00"
        (STATUS_OK, b"?Cal,1"),   # response to "Cal,?"
    ])
    sensor = EzoPhSensor(
        sensor_id="ph",
        interval=0,
        options={"_transport": transport},
    )
    status = sensor.calibrate("mid", 7.0)
    assert status == "?Cal,1"
    assert transport.writes[0][1] == b"Cal,mid,7.00"


def test_ezo_ph_invalid_calibration_point():
    transport = FakeTransport([])
    sensor = EzoPhSensor(
        sensor_id="ph",
        interval=0,
        options={"_transport": transport},
    )
    with pytest.raises(ValueError):
        sensor.calibrate("bogus", 7.0)


def test_ezo_ph_syntax_error_is_raised():
    transport = FakeTransport([(STATUS_SYNTAX_ERROR, b"")])
    sensor = EzoPhSensor(
        sensor_id="ph",
        interval=0,
        options={"_transport": transport},
    )
    with pytest.raises(EzoError):
        list(sensor.read())


# ----- EC -----------------------------------------------------------------


def _ec_setup_responses() -> list[tuple[int, bytes]]:
    """Responses for the 4× O,* commands and 1× K,* command at startup."""
    return [(STATUS_OK, b"")] * 5


def test_ezo_ec_reads_salinity_field():
    transport = FakeTransport(
        _ec_setup_responses()
        + [
            (STATUS_OK, b""),                                   # T,25.00
            (STATUS_OK, b"53000,28000,35.12,1.0264"),           # R
        ]
    )
    sensor = EzoEcSensor(
        sensor_id="sal",
        interval=0,
        options={"_transport": transport, "probe_k": 1.0, "temperature_c": 25.0},
    )
    r = next(iter(sensor.read()))
    assert r.value == pytest.approx(35.12)
    assert r.unit == "PSU"
    assert r.sensor_type == "ezo_ec"


def test_ezo_ec_output_field_selection():
    transport = FakeTransport(
        _ec_setup_responses()
        + [(STATUS_OK, b"53000,28000,35.12,1.0264")]
    )
    sensor = EzoEcSensor(
        sensor_id="ec",
        interval=0,
        options={"_transport": transport, "probe_k": 1.0, "output": "ec"},
    )
    r = next(iter(sensor.read()))
    assert r.value == pytest.approx(53000.0)
    assert r.unit == "µS/cm"


def test_ezo_ec_calibration_low():
    transport = FakeTransport(
        _ec_setup_responses()
        + [
            (STATUS_OK, b""),         # Cal,low,12880
            (STATUS_OK, b"?Cal,1"),   # Cal,?
        ]
    )
    sensor = EzoEcSensor(
        sensor_id="ec",
        interval=0,
        options={"_transport": transport, "probe_k": 1.0},
    )
    status = sensor.calibrate("low", 12880)
    assert status == "?Cal,1"
    # 5 setup writes + Cal write
    assert transport.writes[-2][1] == b"Cal,low,12880"


def test_ezo_ec_dry_calibration_needs_no_value():
    transport = FakeTransport(
        _ec_setup_responses()
        + [
            (STATUS_OK, b""),
            (STATUS_OK, b"?Cal,1"),
        ]
    )
    sensor = EzoEcSensor(
        sensor_id="ec",
        interval=0,
        options={"_transport": transport, "probe_k": 1.0},
    )
    sensor.calibrate("dry")
    assert transport.writes[-2][1] == b"Cal,dry"


def test_ezo_ec_invalid_output_field():
    with pytest.raises(ValueError):
        EzoEcSensor(
            sensor_id="ec",
            interval=0,
            options={"_transport": FakeTransport([]), "output": "rubbish"},
        )


def test_ezo_ec_malformed_response_raises():
    transport = FakeTransport(
        _ec_setup_responses()
        + [(STATUS_OK, b"only,three,values")]
    )
    sensor = EzoEcSensor(
        sensor_id="ec",
        interval=0,
        options={"_transport": transport, "probe_k": 1.0},
    )
    with pytest.raises(EzoError):
        list(sensor.read())
