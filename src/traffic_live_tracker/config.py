from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BusStop:
    id: str
    name: str
    routes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Settings:
    tfl_app_key: str | None
    stops_config_path: Path
    refresh_seconds: int = 30
    tfl_timeout_seconds: float = 10.0


def load_settings() -> Settings:
    return Settings(
        tfl_app_key=os.getenv("TFL_APP_KEY") or None,
        stops_config_path=Path(os.getenv("STOPS_CONFIG_PATH", "config/stops.json")),
        refresh_seconds=_read_int("REFRESH_SECONDS", default=30, minimum=5),
        tfl_timeout_seconds=float(os.getenv("TFL_TIMEOUT_SECONDS", "10")),
    )


def load_stops(path: Path) -> list[BusStop]:
    if not path.exists():
        raise FileNotFoundError(f"Stops config not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Stops config must be a JSON list")

    stops: list[BusStop] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Stop at index {index} must be an object")

        stop_id = _required_string(item, "id", index)
        name = _required_string(item, "name", index)
        routes = item.get("routes", [])
        if routes is None:
            routes = []
        if not isinstance(routes, list) or not all(isinstance(route, str) for route in routes):
            raise ValueError(f"Stop {stop_id} routes must be a list of strings")

        stops.append(BusStop(id=stop_id, name=name, routes=tuple(routes)))

    return stops


def _required_string(item: dict, key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Stop at index {index} must include a non-empty {key}")
    return value.strip()


def _read_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value
