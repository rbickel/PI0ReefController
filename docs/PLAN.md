# PI0 Reef Controller — Plan

## Goal
A lightweight Python service running on a Raspberry Pi Zero (W/2W) that reads
aquarium probes (temperature, pH, ORP, salinity) and publishes their readings
to an MQTT broker so they can be consumed by Home Assistant, Node-RED, or any
other MQTT-aware system.

## Target hardware
- Raspberry Pi Zero / Zero W / Zero 2 W (armv6/armv7, low RAM)
- Raspberry Pi OS Lite (Bookworm), Python 3.11+
- Sensors (planned, in order):
  1. **DS18B20** — 1-Wire temperature probe (GPIO4 by default)
  2. **Red Sea ReefRun pH / Temperature** probe (I²C or USB — TBD on hardware arrival)
  3. **Red Sea ORP** probe (same family — TBD)
  4. **Red Sea Salinity / Temperature** probe (same family — TBD)

## Constraints
- Pi Zero is RAM/CPU constrained → keep dependencies minimal, single process,
  async or thread-per-sensor is fine but no heavy frameworks.
- Network may be flaky → MQTT client must auto-reconnect, publish with QoS 1,
  and use a Last-Will-and-Testament (LWT) `offline` retained message.
- Sensors may be hot-plugged / fail → a failing sensor must not crash the app;
  it should log the error and keep publishing the others.

## Milestones

### M1 — MQTT skeleton with mocked sensors *(this PR)*
- Project scaffolding, config loading, logging.
- `Sensor` abstract base class.
- `MockSensor` that emits plausible random values.
- MQTT client wrapper (paho-mqtt) with reconnect + LWT.
- Main loop: poll each registered sensor on its own interval and publish.
- Unit tests for config + mock sensor + topic formatting.

### M2 — Real DS18B20 driver
- Read `/sys/bus/w1/devices/28-*/w1_slave` (kernel 1-Wire).
- Auto-discover probes by serial; map serial → friendly name in config.
- Integration test guarded by `REEF_HW=1` env var.

### M3 — Atlas EZO-pH probe (I²C)
- Driver talks to the chip over I²C via `smbus2`.
- Optional static temperature compensation; cross-sensor compensation deferred.
- `reef-calibrate ph` CLI for in-situ 3-point calibration.
- Default address `0x63`. EZO chips ship in UART mode → see WIRING.md for the
  one-time switch to I²C.

### M4 — Red Sea ORP probe
- Driver + calibration (single-point at 225 mV or 475 mV).

### M5 — Atlas EZO-EC probe (salinity, I²C)
- Driver returns one of `ec`, `tds`, `salinity`, `sg` per config.
- Probe cell constant (K=1.0) set once and persisted on the chip.
- `reef-calibrate ec` CLI: dry → low (12 880 µS/cm) → high (~80 000 µS/cm).
- Temperature-compensated conductivity → salinity (PSU/ppt).

### M6 — Productionization
- systemd unit, log rotation, Home Assistant MQTT-discovery payloads,
  optional Prometheus textfile exporter.

## MQTT topic design
Base topic configurable, default `reef/`.

```
reef/<sensor_id>/state          → JSON payload, retained
reef/<sensor_id>/availability   → "online" / "offline" (LWT, retained)
reef/bridge/status              → "online" / "offline" (LWT, retained)
```

Example payload (`reef/tank_main_temp/state`):
```json
{
  "value": 25.31,
  "unit": "°C",
  "sensor": "ds18b20",
  "id": "tank_main_temp",
  "ts": "2026-05-11T18:42:03Z"
}
```

For multi-value probes (e.g. pH probe also reports temperature), publish one
topic per measurement:
```
reef/sump_ph/state              → {"value": 8.21, "unit": "pH", ...}
reef/sump_ph_temp/state         → {"value": 25.4, "unit": "°C", ...}
```

## Config (YAML)
See `config.example.yaml`. Each sensor block declares:
- `id` — used in MQTT topic and as a stable identifier
- `type` — driver name (`ds18b20`, `mock`, `redsea_ph`, …)
- `interval` — seconds between reads
- `enabled` — bool
- driver-specific fields (serial, address, calibration, …)

## Test strategy
- **Unit**: drivers receive injected raw-read functions → no hardware needed.
- **Mocks in dev**: set every sensor `type: mock` to validate MQTT end-to-end
  on a laptop against Mosquitto in Docker.
- **Hardware-in-the-loop**: opt-in via env var, runs on the Pi.

## Out of scope (for now)
- Actuators (dosing pumps, relays, lights) — separate future service.
- Web UI — consume via Home Assistant / Grafana.
- Cloud sync.
