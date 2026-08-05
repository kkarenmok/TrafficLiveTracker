from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from traffic_live_tracker.config import BusStop


DEFAULT_STOPS = (
    BusStop(id="490003314R", name="Mare Street / Victoria Park Road Stop R"),
    BusStop(id="490007624S", name="Mare Street / Victoria Park Road Stop Q"),
)


class Base(DeclarativeBase):
    pass


class StopRecord(Base):
    __tablename__ = "bus_stops"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    routes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class DuplicateStopError(ValueError):
    pass


class StopRepository:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self) -> None:
        is_new = not inspect(self.engine).has_table(StopRecord.__tablename__)
        Base.metadata.create_all(self.engine)
        if is_new:
            with self.sessions.begin() as session:
                for position, stop in enumerate(DEFAULT_STOPS):
                    session.add(_record(stop, position))

    def list_stops(self) -> list[BusStop]:
        with self.sessions() as session:
            records = session.scalars(
                select(StopRecord).order_by(StopRecord.position, StopRecord.created_at)
            ).all()
            return [_bus_stop(record) for record in records]

    def add_stop(self, stop: BusStop) -> BusStop:
        with self.sessions() as session:
            next_position = session.scalar(select(func.max(StopRecord.position)))
            session.add(_record(stop, (next_position if next_position is not None else -1) + 1))
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateStopError(stop.id) from exc
        return stop

    def remove_stop(self, stop_id: str) -> BusStop | None:
        with self.sessions.begin() as session:
            record = session.get(StopRecord, stop_id)
            if record is None:
                return None
            stop = _bus_stop(record)
            session.delete(record)
            return stop


def _record(stop: BusStop, position: int) -> StopRecord:
    return StopRecord(id=stop.id, name=stop.name, routes=list(stop.routes), position=position)


def _bus_stop(record: StopRecord) -> BusStop:
    return BusStop(id=record.id, name=record.name, routes=tuple(record.routes or []))
