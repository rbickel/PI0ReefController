# Wiring Plan — Pi Zero + 4 probes

## A note on the "Red Sea" probes
Red Sea (the brand) sells pH / ORP / salinity probes mainly as accessories for
their **ReefBeat** ecosystem (ReefMat, ReefDose, etc.), which is a closed
Bluetooth/Wi-Fi platform. The probes themselves are **standard BNC electrodes**
electrically (pH and ORP) plus a conductivity cell for salinity — they are not
"smart" probes you can plug straight into a Pi.

To read them from a Raspberry Pi you need an **amplifier / transmitter board**
per probe. The two common families are:

| Family               | Bus     | Pros                                   | Cons                          |
|----------------------|---------|----------------------------------------|-------------------------------|
| **Atlas Scientific EZO** (recommended) | I²C     | Production-grade, calibration stored on the chip, isolators available | More expensive (~$40–$50 / probe) |
| DFRobot **Gravity**  | Analog  | Cheap (~$10–$25)                       | Needs ADC, more noise, no on-board calibration |

Below assumes **Atlas Scientific EZO over I²C**, which is by far the cleanest
fit for the Pi Zero. Wiring is identical for genuine Atlas probes or for a
Red Sea BNC probe plugged into the EZO carrier board.

---

## Bill of materials

| Qty | Part                                                              | Purpose                          |
|----:|-------------------------------------------------------------------|----------------------------------|
| 1   | Raspberry Pi Zero 2 W (recommended) or Pi Zero W                  | Controller                       |
| 1   | 5 V / 2.5 A USB-micro PSU (official Pi PSU)                       | Power                            |
| 1   | DS18B20 waterproof probe (with 3-wire cable)                      | Tank temperature                 |
| 1   | 4.7 kΩ resistor (¼ W)                                             | 1-Wire pull-up                   |
| 1   | EZO pH circuit + BNC pH probe (Red Sea or Atlas)                  | pH                               |
| 1   | EZO ORP circuit + BNC ORP probe (Red Sea or Atlas)                | ORP                              |
| 1   | EZO EC (conductivity) circuit + K1.0 conductivity probe           | Salinity                         |
| 3   | Atlas **EZO carrier board** *or* a Whitebox Tentacle/T3 shield    | Mounts EZO chips + provides isolation |
| 1   | Small prototype board / Pi HAT, female headers, 26 AWG wire       | Wiring                           |
| —   | Optional: Adafruit Perma-Proto Pi HAT                             | Tidy assembly                    |

> **Why isolation matters.** pH, ORP and EC probes all sit in the same water.
> Without galvanic isolation between their amplifiers they form a ground loop
> through the water and readings drift / oscillate. The **Whitebox Labs
> Tentacle T3** shield (or the Atlas "EZO Carrier Board with isolator") solves
> this; it hosts all three EZO chips and isolates each I²C channel from the
> Pi. Use it. The DS18B20 is a digital sensor and does not need isolation.

---

## Bus / pin assignment

The Pi Zero exposes the standard 40-pin header.

| Signal       | Pi pin (BCM) | Pi pin (board) | Goes to                                    |
|--------------|:-----------:|:--------------:|--------------------------------------------|
| 3V3          | —           | 1              | EZO carrier VCC, DS18B20 VDD, 4.7 kΩ top    |
| 5V           | —           | 2              | Tentacle T3 VIN (if used; see board docs)   |
| GND          | —           | 6              | Common ground                               |
| **GPIO 2**   | 2           | 3              | I²C SDA → EZO carrier SDA                   |
| **GPIO 3**   | 3           | 5              | I²C SCL → EZO carrier SCL                   |
| **GPIO 4**   | 4           | 7              | 1-Wire DATA (DS18B20) + 4.7 kΩ pull-up to 3V3 |

I²C device addresses (EZO factory defaults):

| Probe                  | EZO module | I²C addr | App sensor id (example) |
|------------------------|------------|---------:|-------------------------|
| pH (+ probe temp comp) | EZO-pH     | `0x63`   | `sump_ph`               |
| ORP                    | EZO-ORP    | `0x62`   | `sump_orp`              |
| Salinity (EC → ppt)    | EZO-EC     | `0x64`   | `sump_salinity`         |

DS18B20 doesn't use I²C — it sits on the 1-Wire bus (GPIO 4) and is auto-
discovered by its 64-bit ROM id: `28-xxxxxxxxxxxx`.

---

## Wiring diagrams

### 1. DS18B20 (1-Wire temperature)

```
                                3V3 (pin 1)
                                  │
                                  ├──── VDD  (red)
                                  │
                          4.7 kΩ  ╪    ┌──────────┐
                                  │    │ DS18B20  │
        GPIO 4 (pin 7) ───────────┴────┤ DATA(yel)│
                                       │          │
                          GND (pin 6) ─┤ GND(blk) │
                                       └──────────┘
```

Notes:
- The pull-up resistor sits between **DATA and 3V3**, not on the probe end.
- Many "waterproof DS18B20" cables already include the resistor in the
  in-line heat-shrink near the connector — if so, **don't add a second one**.
- Multiple DS18B20s can share GPIO 4 (1-Wire is a bus). The driver will
  discover them all; pin a specific probe in config via its `serial:`.

Enable in `/boot/firmware/config.txt` (Bookworm) or `/boot/config.txt` (Bullseye):
```
dtoverlay=w1-gpio
```

### 2. pH / ORP / EC over I²C via Tentacle T3 shield

```
   Pi Zero header                Whitebox Tentacle T3                EZO modules
 ┌─────────────────┐           ┌───────────────────────┐           ┌────────────┐
 │  1   3V3 ───────┼──────────►│ 3V3                   │  socket 1 │   EZO-pH   │── BNC ── pH probe
 │  2   5V  ───────┼──────────►│ VIN                   │           └────────────┘
 │  3   SDA ──────┐│           │  ┌── isolated I²C ──┐ │  socket 2 │   EZO-ORP  │── BNC ── ORP probe
 │  5   SCL ─────┐││           │  │                  │ │           └────────────┘
 │  6   GND ────┐│││           │  └──────────────────┘ │  socket 3 │   EZO-EC   │── 2-pin ── EC probe (K1.0)
 │              ││││           │                       │           └────────────┘
 │  7   GPIO4 → │││├─ to DS18B20                       │
 └──────────────┘│││           └───────────────────────┘
                 │││                  ▲
                 ││└── SDA ───────────┘
                 │└─── SCL
                 └──── GND
```

If you skip the Tentacle shield (not recommended for >1 probe in the same
water), each EZO Carrier Board wires individually:

```
EZO Carrier Board ── VCC → Pi 3V3 (pin 1)
                  ── GND → Pi GND (pin 6 or any GND)
                  ── SDA → Pi GPIO 2 (pin 3)
                  ── SCL → Pi GPIO 3 (pin 5)
                  ── (BNC / 2-pin to the probe)
```

Enable I²C on the Pi:
```bash
sudo raspi-config nonint do_i2c 0
# verify
i2cdetect -y 1
# expected (with EZO defaults):
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 60: --  --  62 63 64 -- -- -- -- ...
```

---

## Full pin map (one-page reference)

```
                Raspberry Pi Zero (40-pin header, top view)
              ┌──────────────────────────────────────────┐
       3V3  1 │■                                       ■ │ 2   5V    ← Tentacle VIN (if used)
       SDA  3 │■   ← I²C to EZO carrier                ■ │ 4   5V
       SCL  5 │■   ← I²C to EZO carrier                ■ │ 6   GND   ← common ground
     GPIO4  7 │■   ← 1-Wire DATA (DS18B20)             ■ │ 8   TXD0
       GND  9 │■                                       ■ │ 10  RXD0
              │  …                                       │
              │  (other pins unused for this project)    │
              └──────────────────────────────────────────┘
```

Unused pins are free for future actuators (relays, dosing pumps) — that
extension lives in a separate service per the plan.

---

## Power budget (rough)

| Consumer                       | Typical |
|--------------------------------|--------:|
| Pi Zero 2 W idle               | 120 mA  |
| Pi Zero 2 W Wi-Fi active       | 250 mA  |
| DS18B20                        | 1 mA    |
| Each EZO module (idle)         | 5 mA    |
| Each EZO module (reading)      | 12 mA   |
| Tentacle T3 isolators (3 ch)   | ~30 mA  |
| **Total worst-case**           | ~310 mA |

A 2.5 A official Pi PSU has huge headroom. Keep the USB cable short and
thick — voltage sag is the most common gremlin on Pi Zero.

---

## Calibration recap (do this once, then again every few months)

| Probe    | Solutions                              | Notes                                                  |
|----------|----------------------------------------|--------------------------------------------------------|
| pH       | pH 7.00 (mid), then 4.00 and/or 10.00  | Always start with mid. Rinse with RO between buffers.  |
| ORP      | 225 mV (or 400 mV) reference solution  | Single-point.                                          |
| EC (salt)| 12 880 µS (or 53 000 µS for marine)    | Use a marine-range standard close to 35 ppt = ~53 mS.  |
| DS18B20  | None                                   | Factory ±0.5 °C; if needed, software offset in config. |

EZO modules persist their calibration internally, so the Pi can be reflashed
without losing it.

---

## Mapping back to the application

Each line in `config.yaml` already targets one of these probes. Once the
hardware is in place, swap the mock entries for real ones:

```yaml
sensors:
  - id: tank_main_temp
    type: ds18b20            # 1-Wire on GPIO4
    interval: 10
    enabled: true
    # serial: 28-0000abcdef12   # leave unset to auto-pick the first probe

  - id: sump_ph
    type: redsea_ph           # driver to be added in M3 → talks I²C @ 0x63
    interval: 15
    enabled: false
    address: 0x63

  - id: sump_orp
    type: redsea_orp          # M4 → I²C @ 0x62
    interval: 15
    enabled: false
    address: 0x62

  - id: sump_salinity
    type: redsea_salinity     # M5 → I²C @ 0x64
    interval: 30
    enabled: false
    address: 0x64
```

The drivers themselves (`redsea_ph`, `redsea_orp`, `redsea_salinity`) land in
milestones M3–M5; until then the mock entries in
[config.example.yaml](../config.example.yaml) exercise the MQTT pipeline.
