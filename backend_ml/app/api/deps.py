from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Robot
from app.services import queries
from app.services.ingest import now_ms


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.db.session() as session:
        yield session


def get_robot_or_404(robot_id: str, session: Session = Depends(get_session)) -> Robot:
    robot = queries.get_robot(session, robot_id)
    if robot is None:
        raise HTTPException(status_code=404, detail=f"robot '{robot_id}' not found")
    return robot


def is_online(robot: Robot, settings: Settings) -> bool:
    return now_ms() - robot.last_seen_ms <= settings.robot_online_timeout_s * 1000


@dataclass
class TimeRange:
    from_ms: int
    to_ms: int


def get_time_range(
    robot: Robot = Depends(get_robot_or_404),
    settings: Settings = Depends(get_settings_dep),
    from_ms: int | None = Query(None, description="начало диапазона, unix-время в мс"),
    to_ms: int | None = Query(None, description="конец диапазона, unix-время в мс"),
    window_s: int | None = Query(
        None, gt=0, description="если from_ms не задан — сколько секунд назад от to_ms брать"
    ),
) -> TimeRange:
    """По умолчанию: последние default_window_s секунд до самой свежей точки робота."""
    end = to_ms if to_ms is not None else (robot.last_point_ms or now_ms())
    if from_ms is not None:
        start = from_ms
    else:
        start = end - (window_s or settings.default_window_s) * 1000
    if start > end:
        raise HTTPException(status_code=422, detail="from_ms must be <= to_ms")
    return TimeRange(start, end)
