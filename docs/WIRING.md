# Wiring Plan — Pi Zero + 4 probes

## Ordered hardware (Phase 2 BoM)

The following parts have been ordered from
[sensorsandprobes.com](https://sensorsandprobes.com/) (the reseller now handling
the wound-down Whitebox Labs catalogue):

| # | Part | Purpose |
|---|------|---------|
| 1 | [Whitebox T5 for Raspberry Pi](https://sensorsandprobes.com/products/whitebox-t5-for-raspberry-pi) | Pi-Zero pHAT hosting 1× isolated EZO slot + 1× RTD slot (I²C only) |
| 2 | [Atlas Lab-Grade pH Probe](https://sensorsandprobes.com/products/lab-grade-ph-probe) | BNC pH electrode |
| 3 | [Atlas Conductivity Probe K=1.0](https://sensorsandprobes.com/products/conductivity-probe-k-1-0) | 2-pin conductivity cell (salinity) |

### Still required to complete this phase

| Part | Why | Approx. price |
|------|-----|---------------|
| **EZO-pH circuit** | Amplifier/ADC for the pH probe | ~CHF 45 |
| **EZO-EC circuit** | Amplifier/ADC for the EC probe | ~CHF 45 |
| **A 2nd carrier slot for EC** — pick one: | The T5 has only 1 non-RTD slot. | |
| &nbsp;&nbsp;&nbsp;a) A second Whitebox T5 (stacked) | Cleanest, gives 2 isolated + 2 RTD slots | ~CHF 17 |
| &nbsp;&nbsp;&nbsp;b) Atlas EZO Carrier Board + PWR-ISO | Standalone, wires to same I²C bus | ~CHF 30 |

The application code is identical for both options — the EZO chip's I²C
address is what the driver targets, not the carrier board it sits on.

### Already on the bench (Phase 1)

- Raspberry Pi Zero 2 W + official 5 V / 2.5 A PSU
- DS18B20 waterproof temperature probe + 4.7 kΩ pull-up

---

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
| **Atlas Scientific EZO** (recommended, ordered) | I²C     | Production-grade, calibration stored on the chip, isolators available | More expensive (~$40–$50 / probe) |
| DFRobot **Gravity**  | Analog  | Cheap (~$10–$25)                       | Needs ADC, more noise, no on-board calibration |

Below assumes **Atlas Scientific EZO over I²C**, which is by far the cleanest
fit for the Pi Zero. Wiring is identical for genuine Atlas probes or for a
generic BNC probe plugged into the EZO carrier board.

---
## Bill of materials (full project, all 4 probes)

| Qty | Part                                                              | Purpose                          |
|----:|-------------------------------------------------------------------|----------------------------------|
| 1   | Raspberry Pi Zero 2 W (recommended) or Pi Zero W                  | Controller                       |
| 1   | 5 V / 2.5 A USB-micro PSU (official Pi PSU)                       | Power                            |
| 1   | DS18B20 waterproof probe (with 3-wire cable)                      | Tank temperature                 |
| 1   | 4.7 kΩ resistor (¼ W)                                             | 1-Wire pull-up                   |
| 2   | **Whitebox T5 for Raspberry Pi** (stacked)                        | Hosts EZO chips + provides isolation |
| 1   | EZO-pH circuit + BNC pH probe                                     | pH                               |
| 1   | EZO-ORP circuit + BNC ORP probe                                   | ORP (added in M4)                |
| 1   | EZO-EC circuit + K=1.0 conductivity probe                         | Salinity                         |
| —   | Optional: EZO-RTD + Pt-1000 probe                                 | Replaces DS18B20 for higher accuracy |
| 1   | Small prototype board, jumper wires                               | Wiring                           |

> **Why isolation matters.** pH, ORP and EC probes all sit in the same water.
> Without galvanic isolation between their amplifiers they form a ground loop
> through the water and readings drift / oscillate. The **Whitebox T5** solves
> this for the chip in its isolated slot. The DS18B20 is a digital sensor and
> does not need isolation.

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

### 2. pH / EC over I²C via Whitebox T5 (ordered hardware)

The T5 is a Pi pHAT with:
- **1 isolated EZO slot** (for EZO-pH, EZO-ORP, EZO-DO or EZO-EC — *not* EZO-RTD)
- **1 non-isolated RTD slot** (only fits the EZO-RTD)
- Stackable: two T5s give 2 isolated + 2 RTD slots
- **I²C only**. The EZO chips ship in UART mode — see "First-time setup" below
  for the one-time switch.

Recommended population for this project:

```
Pi Zero 2 W
   └── T5  #1            ← ordered now
   │      ├── isolated:  EZO-pH    → BNC → Lab-grade pH probe
   │      └── RTD slot:  EZO-RTD   → screw → Pt-1000 (future; replaces DS18B20 if you want)
   └── T5  #2            ← buy later (or use a standalone carrier)
          ├── isolated:  EZO-EC    → 2-pin screw → K=1.0 EC probe
          └── RTD slot:  unused (or 2nd EZO-RTD)
```

Until the second carrier arrives, the DS18B20 on GPIO 4 covers temperature
and only **pH** runs through the T5.

```
   Pi Zero header              Whitebox T5 (#1, stacked on header)
 ┌─────────────────┐         ┌────────────────────────────────────┐
 │  1   3V3 ───────┼────────►│ 3V3                                │
 │  2   5V  ───────┼────────►│ VIN                                │
 │  3   SDA ──────►│ ───────►│ I²C SDA  → isolated EZO-pH (0x63)  │── BNC ── pH probe
 │  5   SCL ──────►│ ───────►│ I²C SCL  → RTD slot (future)       │── screw ── Pt-1000
 │  6   GND ──────►│ ───────►│ GND                                │
 │  7   GPIO4 ─────┼─── to DS18B20 (1-Wire bypasses the T5)       │
 └─────────────────┘         └────────────────────────────────────┘
```

For the EC chip on a second T5 / standalone carrier, the wiring is the same:
share VCC + GND + SDA + SCL with the Pi (or pass through the first T5's
unused header pins, which are looped through by design).

### First-time EZO setup (run once per chip)

EZO chips ship in **UART mode** by default. The T5 is I²C-only, so you must
switch each chip to I²C the first time. Two ways:

**Option 1 — using the T5 itself, one chip at a time:**

1. Power off the Pi.
2. Plug *one* EZO chip into the T5's isolated slot, with **no probe** attached
   and **no other EZO on the bus**.
3. Boot the Pi. The chip is initially in UART mode and won't appear on I²C
   yet, but the T5 routes UART through the Pi's GPIO 14/15 (TXD/RXD).
4. From the Pi:
   ```bash
   sudo raspi-config nonint do_serial_hw 0      # enable hardware UART
   sudo raspi-config nonint do_serial_cons 1    # but disable login console
   sudo reboot
   ```
5. Send the I²C-mode command (each EZO has a default address it falls into):
   ```bash
   # pH → 0x63, ORP → 0x62, EC → 0x64, RTD → 0x66, DO → 0x61
   echo -e "I2C,99\r" > /dev/serial0    # 99 = use default address
   sleep 2
   ```
6. Power off, install the chip in its final slot, boot back up. Verify with
   `i2cdetect -y 1`.

**Option 2 — Atlas's USB-to-EZO debugger cable** (~CHF 25): plug each chip
into the cable, talk to it from your laptop with a serial terminal, send
`I2C,99`. Faster if you're setting up multiple chips.

You only do this once per chip. The setting persists across power cycles.

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
       3V3  1 │■                                       ■ │ 2   5V    ← T5 VIN (if used)
       SDA  3 │■   ← I²C to T5 / EZO carrier           ■ │ 4   5V
       SCL  5 │■   ← I²C to T5 / EZO carrier           ■ │ 6   GND   ← common ground
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
| T5 isolator (per board)        | ~10 mA  |
| **Total worst-case**           | ~310 mA |

A 2.5 A official Pi PSU has huge headroom. Keep the USB cable short and
thick — voltage sag is the most common gremlin on Pi Zero.

---

## Calibration

### What to buy

| Probe    | Solutions                              | Notes                                                  |
|----------|----------------------------------------|--------------------------------------------------------|
| pH       | pH 7.00 (mid), then 4.00 and/or 10.00  | Always start with mid. Rinse with RO between buffers.  |
| ORP      | 225 mV (or 475 mV) reference solution  | Single-point.                                          |
| EC (salt)| 12 880 µS (low) **and** ~53 000 µS (high, marine) | Two-point calibration for the marine range. 35 ppt ≈ 53 mS. |
| DS18B20  | None                                   | Factory ±0.5 °C; if needed, software offset in config. |

EZO modules persist their calibration internally, so the Pi can be reflashed
without losing calibration.

### Doing it from the Pi — `reef-calibrate` CLI

The app ships a `reef-calibrate` command that talks directly to the EZO chips
over I²C, so you don't need a separate USB-EZO debugger cable to recalibrate.
You should **stop the main service** first so it doesn't fight for the I²C bus.

```bash
sudo systemctl stop reef-controller     # if running as a service

# --- pH (3-point) ---
python -m reef_controller.cli.calibrate ph --status
python -m reef_controller.cli.calibrate ph --mid 7.00     # always first!
python -m reef_controller.cli.calibrate ph --low 4.00
python -m reef_controller.cli.calibrate ph --high 10.00

# --- EC / salinity (2-point) ---
python -m reef_controller.cli.calibrate ec --probe-k 1.0  # one-time
python -m reef_controller.cli.calibrate ec --dry          # in air, before liquids
python -m reef_controller.cli.calibrate ec --low 12880    # 12.88 mS standard
python -m reef_controller.cli.calibrate ec --high 80000   # marine standard

# Inspect / clear
python -m reef_controller.cli.calibrate ph --status
python -m reef_controller.cli.calibrate ec --clear
```

Procedure for each point:

1. Rinse the probe in RO/DI water, shake off (don't wipe).
2. Submerge 3 cm into the calibration solution. Stir gently 10 s, then wait
   for the live reading shown by the CLI to stabilise (drift < ±0.02 pH or
   < ±50 µS over 30 s).
3. Press <kbd>Enter</kbd> in the CLI to commit the point.

The CLI prints a 1 Hz live reading while you wait, then commits and shows the
resulting calibration status. Repeat **every 3–6 months** for a reef tank.

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
    type: ezo_ph              # I²C @ 0x63 (Atlas EZO-pH)
    interval: 15
    enabled: false            # flip to true once the chip is wired up
    address: 0x63
    # Optional: compensate readings against another sensor's temperature.
    # For now you can pass a static temperature_c instead.
    temperature_c: 25.0

  - id: sump_orp
    type: ezo_orp             # M4 → I²C @ 0x62
    interval: 15
    enabled: false
    address: 0x62

  - id: sump_salinity
    type: ezo_ec              # I²C @ 0x64 (Atlas EZO-EC)
    interval: 30
    enabled: false
    address: 0x64
    probe_k: 1.0              # one-time, also set via the calibrate CLI
    output: salinity          # one of: ec, tds, salinity, sg
    temperature_c: 25.0
```
