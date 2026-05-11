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
- [ ] M3 — Red Sea pH/Temp driver
- [ ] M4 — Red Sea ORP driver
- [ ] M5 — Red Sea Salinity/Temp driver

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
