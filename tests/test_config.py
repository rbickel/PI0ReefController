from pathlib import Path

from reef_controller.config import load_config


def test_load_example_config(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    cfg = load_config(example)
    assert cfg.mqtt.host == "localhost"
    assert cfg.mqtt.base_topic == "reef"
    assert len(cfg.sensors) >= 1
    first = cfg.sensors[0]
    assert first.id == "tank_main_temp"
    assert first.type == "mock"
    assert "min" in first.options and "max" in first.options
