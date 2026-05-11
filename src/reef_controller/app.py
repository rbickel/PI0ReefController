"""Application entry point and main polling loop."""
from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from heapq import heappop, heappush
from typing import List, Tuple

from .config import AppConfig, load_config
from .mqtt_client import MqttClient
from .sensors import Sensor, build_sensor

log = logging.getLogger("reef_controller")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


class Controller:
    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        self._mqtt = MqttClient(cfg.mqtt)
        self._sensors: List[Sensor] = []
        self._failures: dict[str, int] = {}
        self._stop = threading.Event()

        for s_cfg in cfg.sensors:
            if not s_cfg.enabled:
                log.info("Sensor %s disabled, skipping", s_cfg.id)
                continue
            try:
                self._sensors.append(build_sensor(s_cfg))
            except Exception as exc:
                log.error("Failed to build sensor %s: %s", s_cfg.id, exc)

        if not self._sensors:
            log.warning("No sensors enabled — the bridge will still publish its status.")

    # --- main loop -------------------------------------------------------

    def run(self) -> None:
        self._mqtt.start()
        if not self._mqtt.wait_until_connected(timeout=10):
            log.warning("MQTT not connected after 10s; continuing (paho will retry).")

        # Priority queue of (next_run_epoch, sensor_index).
        queue: list[Tuple[float, int]] = []
        now = time.monotonic()
        for i, _ in enumerate(self._sensors):
            heappush(queue, (now, i))

        try:
            while not self._stop.is_set() and queue:
                next_run, idx = queue[0]
                wait = max(0.0, next_run - time.monotonic())
                if self._stop.wait(timeout=wait):
                    break
                heappop(queue)
                sensor = self._sensors[idx]
                self._poll_one(sensor)
                heappush(queue, (time.monotonic() + sensor.interval, idx))
        finally:
            self._shutdown()

    def _poll_one(self, sensor: Sensor) -> None:
        try:
            readings = list(sensor.read())
        except Exception as exc:
            count = self._failures.get(sensor.id, 0) + 1
            self._failures[sensor.id] = count
            log.warning("Sensor %s read failed (%d): %s", sensor.id, count, exc)
            if count >= self._cfg.failure_threshold:
                self._mqtt.set_availability(sensor.id, online=False)
            return

        self._failures[sensor.id] = 0
        self._mqtt.set_availability(sensor.id, online=True)
        for r in readings:
            self._mqtt.publish_reading(r)

    # --- shutdown --------------------------------------------------------

    def request_stop(self, *_args) -> None:
        log.info("Stop requested")
        self._stop.set()

    def _shutdown(self) -> None:
        for s in self._sensors:
            try:
                s.close()
            except Exception:
                log.exception("Error closing sensor %s", s.id)
        self._mqtt.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reef_controller")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to YAML config")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    _setup_logging(cfg.log_level)
    log.info("Starting reef_controller with %d sensor(s)", len(cfg.sensors))

    controller = Controller(cfg)
    signal.signal(signal.SIGINT, controller.request_stop)
    signal.signal(signal.SIGTERM, controller.request_stop)
    controller.run()
    return 0
