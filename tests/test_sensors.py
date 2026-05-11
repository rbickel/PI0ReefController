import pytest

from reef_controller.sensors.ds18b20 import DS18B20Sensor, parse_w1_slave
from reef_controller.sensors.mock import MockSensor


def test_mock_sensor_value_within_bounds():
    s = MockSensor("t1", interval=1, options={"min": 10, "max": 11, "unit": "°C"})
    for _ in range(50):
        readings = list(s.read())
        assert len(readings) == 1
        r = readings[0]
        assert r.sensor_id == "t1"
        assert r.unit == "°C"
        assert 10.0 <= r.value <= 11.0


def test_mock_payload_shape():
    s = MockSensor("t1", interval=1, options={"min": 1, "max": 2})
    r = next(iter(s.read()))
    p = r.to_payload()
    assert set(p) == {"value", "unit", "sensor", "id", "ts"}


def test_parse_w1_slave_ok():
    raw = (
        "72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n"
        "72 01 4b 46 7f ff 0e 10 57 t=23125\n"
    )
    assert parse_w1_slave(raw) == pytest.approx(23.125)


def test_parse_w1_slave_crc_fail():
    raw = (
        "72 01 4b 46 7f ff 0e 10 57 : crc=57 NO\n"
        "72 01 4b 46 7f ff 0e 10 57 t=23125\n"
    )
    with pytest.raises(IOError):
        parse_w1_slave(raw)


def test_ds18b20_with_injected_reader():
    raw = (
        "72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n"
        "72 01 4b 46 7f ff 0e 10 57 t=24500\n"
    )
    sensor = DS18B20Sensor(
        "tank",
        interval=10,
        options={"serial": "28-deadbeef", "_reader": lambda _s: raw},
    )
    r = next(iter(sensor.read()))
    assert r.sensor_type == "ds18b20"
    assert r.value == pytest.approx(24.5)
    assert r.unit == "°C"
