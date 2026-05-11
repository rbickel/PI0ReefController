# PI0 Reef Controller

Python service for Raspberry Pi Zero that reads aquarium probes and publishes
their values to an MQTT broker.

## Documentation

Start here, in this order:

| Doc | What's inside |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Goals, constraints, milestones M1–M6, MQTT topic design, test strategy |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module diagram, key abstractions (`Sensor`, `Reading`, `MqttClient`), failure-handling matrix |
| [docs/WIRING.md](docs/WIRING.md) | Hardware bill of materials, Pi Zero pin map, wiring diagrams for the 4 probes, calibration notes |
| [config.example.yaml](config.example.yaml) | Annotated template config — copy to `config.yaml` and edit |

## Status
- [x] M1 — MQTT skeleton with mocked sensors
- [ ] M2 — DS18B20 driver
- [x] M3 — Atlas EZO-pH driver + calibration CLI
- [ ] M4 — Atlas EZO-ORP driver
- [x] M5 — Atlas EZO-EC (salinity) driver + calibration CLI

## Quick start (dev, on a laptop)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy config.example.yaml config.yaml

# Run a local broker (Docker):
docker run -it --rm -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf

# In another shell, run the controller:
python -m reef_controller --config config.yaml

# In a third shell, watch the topics:
docker run -it --rm --network host eclipse-mosquitto:2 mosquitto_sub -h localhost -t 'reef/#' -v
```

## Run on the Pi

```bash
sudo apt install python3-venv python3-pip
python3 -m venv ~/reef/.venv
~/reef/.venv/bin/pip install -r requirements.txt
~/reef/.venv/bin/python -m reef_controller --config ~/reef/config.yaml
```

A systemd unit will be added in M6.

## Tests
```powershell
pytest
```

## Probe calibration

Once the EZO chips are wired up, calibrate them in-situ from the Pi:

```bash
sudo systemctl stop reef-controller   # if running as a service

# pH (always start with the mid-point buffer)
python -m reef_controller.cli.calibrate ph --mid 7.00
python -m reef_controller.cli.calibrate ph --low 4.00
python -m reef_controller.cli.calibrate ph --high 10.00

# EC / salinity
python -m reef_controller.cli.calibrate ec --probe-k 1.0
python -m reef_controller.cli.calibrate ec --dry
python -m reef_controller.cli.calibrate ec --low 12880
python -m reef_controller.cli.calibrate ec --high 80000

# Inspect / clear
python -m reef_controller.cli.calibrate ph --status
python -m reef_controller.cli.calibrate ec --clear
```

Calibration data lives on the EZO chip itself, so you can reflash the Pi
without losing it. See [docs/WIRING.md](docs/WIRING.md) for the procedure
and solutions to buy.

## Project layout
```
src/reef_controller/   # application package
docs/                  # design docs — see Documentation section above
tests/                 # pytest suite
config.example.yaml    # template config
```

## See also
- [docs/PLAN.md](docs/PLAN.md) — roadmap & milestones
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — internal design
- [docs/WIRING.md](docs/WIRING.md) — hardware & wiring
