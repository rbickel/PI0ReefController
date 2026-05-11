"""Interactive calibration CLI for EZO probes.

Usage:
    python -m reef_controller.cli.calibrate ph  --status
    python -m reef_controller.cli.calibrate ph  --mid 7.00
    python -m reef_controller.cli.calibrate ph  --low 4.00
    python -m reef_controller.cli.calibrate ph  --high 10.00
    python -m reef_controller.cli.calibrate ph  --clear

    python -m reef_controller.cli.calibrate ec  --status
    python -m reef_controller.cli.calibrate ec  --probe-k 1.0
    python -m reef_controller.cli.calibrate ec  --dry
    python -m reef_controller.cli.calibrate ec  --low  12880
    python -m reef_controller.cli.calibrate ec  --high 80000
    python -m reef_controller.cli.calibrate ec  --clear

Common options:
    --address 0x63        Override the chip's I²C address.
    --bus 1               Override the I²C bus number (default 1).
    --no-wait             Skip the interactive "press Enter when stable" prompt.

The CLI prints a live reading (1 Hz) until you press Enter, then commits the
point. Stop the main service first so it doesn't fight for the I²C bus.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Callable

from ..sensors.ezo import EzoError
from ..sensors.ezo_ec import EzoEcSensor
from ..sensors.ezo_ph import EzoPhSensor

log = logging.getLogger("reef_controller.cli.calibrate")


# ---------- helpers ---------------------------------------------------------

def _live_read(read_fn: Callable[[], float], label: str, *, wait: bool) -> None:
    """Print a 1 Hz live reading until Enter is pressed (or once if no-wait)."""
    if not wait:
        try:
            value = read_fn()
            print(f"{label}: {value}")
        except EzoError as exc:
            print(f"read error: {exc}", file=sys.stderr)
        return

    print(f"Hold the probe in the solution. Live {label} reading shown below.")
    print("Press Enter when the reading is stable to commit, or Ctrl-C to abort.")
    print("---")
    import select

    while True:
        try:
            value = read_fn()
            print(f"  {label}: {value}    ", end="\r", flush=True)
        except EzoError as exc:
            print(f"  read error: {exc}     ", end="\r", flush=True)

        # Poll stdin for ~1 s; if the user hit Enter, commit.
        ready, _, _ = select.select([sys.stdin], [], [], 1.0)
        if ready:
            sys.stdin.readline()
            print()
            return


def _read_ph(sensor: EzoPhSensor) -> float:
    return next(iter(sensor.read())).value


def _read_ec(sensor: EzoEcSensor) -> float:
    return next(iter(sensor.read())).value


# ---------- pH --------------------------------------------------------------

def _build_ph(args: argparse.Namespace) -> EzoPhSensor:
    return EzoPhSensor(
        sensor_id="cli_ph",
        interval=0,
        options={
            "address": int(args.address, 0) if isinstance(args.address, str) else args.address,
            "bus": args.bus,
        },
    )


def _cmd_ph(args: argparse.Namespace) -> int:
    sensor = _build_ph(args)

    if args.status:
        print(sensor.calibration_status())
        return 0
    if args.clear:
        sensor.clear_calibration()
        print("pH calibration cleared.")
        print(sensor.calibration_status())
        return 0

    for point, value in (("mid", args.mid), ("low", args.low), ("high", args.high)):
        if value is None:
            continue
        _live_read(lambda: _read_ph(sensor), label=f"pH (target {value})", wait=not args.no_wait)
        status = sensor.calibrate(point, value)
        print(f"Committed {point} @ {value}. Status: {status}")
    return 0


# ---------- EC --------------------------------------------------------------

def _build_ec(args: argparse.Namespace) -> EzoEcSensor:
    return EzoEcSensor(
        sensor_id="cli_ec",
        interval=0,
        options={
            "address": int(args.address, 0) if isinstance(args.address, str) else args.address,
            "bus": args.bus,
            "output": "ec",       # calibrate against raw µS/cm
        },
    )


def _cmd_ec(args: argparse.Namespace) -> int:
    sensor = _build_ec(args)

    if args.probe_k is not None:
        sensor.set_probe_k(args.probe_k)
        print(f"Probe K set to {args.probe_k}.")

    if args.status:
        print(sensor.calibration_status())
        return 0
    if args.clear:
        sensor.clear_calibration()
        print("EC calibration cleared.")
        print(sensor.calibration_status())
        return 0
    if args.dry:
        print("Make sure the probe is bone dry and in open air.")
        if not args.no_wait:
            input("Press Enter to commit the dry calibration... ")
        status = sensor.calibrate("dry")
        print(f"Committed dry. Status: {status}")

    for point, value in (("low", args.low), ("high", args.high), ("single", args.single)):
        if value is None:
            continue
        _live_read(lambda: _read_ec(sensor), label=f"EC µS/cm (target {value})", wait=not args.no_wait)
        status = sensor.calibrate(point, value)
        print(f"Committed {point} @ {value} µS/cm. Status: {status}")
    return 0


# ---------- argparse glue ---------------------------------------------------

def _add_common(p: argparse.ArgumentParser, default_addr: int) -> None:
    p.add_argument("--address", default=default_addr,
                   help=f"I²C address (default 0x{default_addr:02x})")
    p.add_argument("--bus", type=int, default=1, help="I²C bus number (default 1)")
    p.add_argument("--no-wait", action="store_true",
                   help="Don't wait for Enter; commit immediately after one read")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reef_controller.cli.calibrate")
    sub = parser.add_subparsers(dest="probe", required=True)

    ph = sub.add_parser("ph", help="Calibrate the EZO-pH circuit")
    _add_common(ph, 0x63)
    ph.add_argument("--status", action="store_true", help="Show calibration status and exit")
    ph.add_argument("--clear", action="store_true", help="Clear all pH calibration points")
    ph.add_argument("--mid", type=float, help="Mid-point pH value (do this first!)")
    ph.add_argument("--low", type=float, help="Low-point pH value (e.g. 4.00)")
    ph.add_argument("--high", type=float, help="High-point pH value (e.g. 10.00)")
    ph.set_defaults(func=_cmd_ph)

    ec = sub.add_parser("ec", help="Calibrate the EZO-EC circuit")
    _add_common(ec, 0x64)
    ec.add_argument("--probe-k", type=float, dest="probe_k",
                    help="Set the probe's K value (one-time, persists)")
    ec.add_argument("--status", action="store_true", help="Show calibration status and exit")
    ec.add_argument("--clear", action="store_true", help="Clear all EC calibration points")
    ec.add_argument("--dry", action="store_true",
                    help="Dry calibration (probe in air, before any liquid)")
    ec.add_argument("--low", type=float, help="Low-point standard in µS/cm (e.g. 12880)")
    ec.add_argument("--high", type=float, help="High-point standard in µS/cm (e.g. 80000)")
    ec.add_argument("--single", type=float, help="Single-point calibration in µS/cm")
    ec.set_defaults(func=_cmd_ec)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except EzoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
