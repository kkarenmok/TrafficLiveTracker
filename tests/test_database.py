from pathlib import Path

import pytest

from traffic_live_tracker.config import BusStop
from traffic_live_tracker.database import DuplicateStopError, StopRepository


def repository(tmp_path: Path) -> StopRepository:
    repo = StopRepository(f"sqlite:///{tmp_path / 'stops.db'}")
    repo.initialize()
    return repo


def test_new_database_is_seeded_once(tmp_path: Path):
    repo = repository(tmp_path)

    assert [stop.id for stop in repo.list_stops()] == ["490003314R", "490007624S"]

    repo.remove_stop("490003314R")
    repo.remove_stop("490007624S")
    repo.initialize()

    assert repo.list_stops() == []


def test_repository_adds_removes_and_preserves_routes(tmp_path: Path):
    repo = repository(tmp_path)
    stop = BusStop(id="490000001A", name="Test Stop A", routes=("12", "24"))

    repo.add_stop(stop)
    assert repo.list_stops()[-1] == stop
    assert repo.remove_stop(stop.id) == stop
    assert repo.remove_stop(stop.id) is None


def test_repository_rejects_duplicate_stop(tmp_path: Path):
    repo = repository(tmp_path)

    with pytest.raises(DuplicateStopError):
        repo.add_stop(BusStop(id="490003314R", name="Duplicate"))
