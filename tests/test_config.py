from pathlib import Path

import pytest

from traffic_live_tracker.config import load_stops


def test_load_stops_reads_valid_config(tmp_path: Path):
    config = tmp_path / "stops.json"
    config.write_text(
        '[{"id": "490000091A", "name": "Example Stop", "routes": ["12"]}]',
        encoding="utf-8",
    )

    stops = load_stops(config)

    assert stops[0].id == "490000091A"
    assert stops[0].name == "Example Stop"
    assert stops[0].routes == ("12",)


def test_load_stops_rejects_missing_name(tmp_path: Path):
    config = tmp_path / "stops.json"
    config.write_text('[{"id": "490000091A"}]', encoding="utf-8")

    with pytest.raises(ValueError, match="name"):
        load_stops(config)
