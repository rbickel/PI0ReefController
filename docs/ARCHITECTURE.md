# Architecture

```
                        ┌─────────────────────────────────┐
                        │           app.py                │
                        │   (load config → build sensors  │
                        │    → start scheduler → publish) │
                        └───────────────┬─────────────────┘
                                        │
                ┌───────────────────────┼────────────────────────┐
                ▼                       ▼                        ▼
        ┌──────────────┐        ┌──────────────┐         ┌──────────────┐
        │  Sensor (ABC)│        │ MqttClient   │         │   Config     │
        └──────┬───────┘        │ (paho, LWT,  │         │ (YAML loader)│
               │                │  reconnect)  │         └──────────────┘
   ┌───────────┼───────────┐    └──────────────┘
   ▼           ▼           ▼
┌──────┐  ┌────────┐  ┌─────────┐
│ Mock │  │DS18B20 │  │ RedSea* │  (added in later milestones)
└──────┘  └────────┘  └─────────┘
```

## Module layout
```
src/reef_controller/
├── __init__.py
├── __main__.py            # python -m reef_controller
├── app.py                 # orchestration / main loop
├── config.py              # dataclasses + YAML loader
├── mqtt_client.py         # paho-mqtt wrapper
├── scheduler.py           # per-sensor polling (threading.Timer-based)
└── sensors/
    ├── __init__.py
    ├── base.py            # Sensor ABC + Reading dataclass
    ├── registry.py        # type-name → class map
    ├── mock.py            # MockSensor
    └── ds18b20.py         # 1-Wire temperature driver
```

## Key abstractions

### `Reading`
```python
@dataclass(frozen=True)
class Reading:
    sensor_id: str      # "tank_main_temp"
    value: float
    unit: str           # "°C", "pH", "mV", "ppt"
    sensor_type: str    # "ds18b20"
    timestamp: datetime # UTC
```

### `Sensor` (ABC)
```python
class Sensor(ABC):
    id: str
    interval: float

    @abstractmethod
    def read(self) -> Iterable[Reading]:
        """Return one or more readings. Raise on transient failure."""
```
A single physical probe may emit multiple `Reading`s (e.g. pH + temp).

### `MqttClient`
- Wraps `paho.mqtt.client.Client`.
- Configures LWT on `<base>/bridge/status` = `offline` retained.
- Publishes per-sensor `<base>/<id>/availability` = `online` retained on first
  successful read, `offline` on N consecutive failures.
- Reading → JSON payload published to `<base>/<id>/state` retained, QoS 1.

### Scheduler
- One `threading.Timer` per sensor (or a single loop iterating sensors with
  next-due timestamps). On Pi 0 we keep it to one background thread and a
  priority queue; cheap and predictable.
- Failures are caught, logged, counted; sensor availability flips to
  `offline` after `failure_threshold` consecutive errors.

## Failure handling matrix
| Condition                    | Behavior                                   |
|------------------------------|--------------------------------------------|
| Sensor read raises           | log warn, increment failure counter        |
| Failures ≥ threshold         | publish availability=offline (retained)    |
| Sensor recovers              | publish availability=online                |
| MQTT broker disconnects      | paho auto-reconnect with backoff           |
| Process exits / crashes      | LWT flips bridge/status to offline         |

## Why these choices
- **paho-mqtt** — de-facto standard, tiny, works on armv6.
- **PyYAML** — config is human-edited; YAML > JSON for comments.
- **No asyncio** — Pi Zero has 1 core; threads + blocking I/O are simpler and
  the workload is trivially low-rate (≥ 1 s intervals).
- **stdlib logging** — journald picks it up via systemd.
