from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import TimeRange, get_robot_or_404, get_session, get_settings_dep, get_time_range
from app.config import Settings
from app.models import Robot
from app.schemas import EventsOut, Metrics, MetricsTimeseries
from app.services import queries
from app.services.metrics import compute_metrics, compute_timeseries, detect_events

router = APIRouter(prefix="/api/robots/{robot_id}", tags=["metrics"])


@router.get("/metrics", response_model=Metrics, summary="Сводные метрики за диапазон")
def get_metrics(
    robot: Robot = Depends(get_robot_or_404),
    rng: TimeRange = Depends(get_time_range),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    points = queries.points_in_range(session, robot.id, rng.from_ms, rng.to_ms)
    m = compute_metrics(points, idle_eps=settings.idle_speed_eps, max_gap_ms=settings.max_gap_ms)
    return Metrics(robot_id=robot.id, from_ms=rng.from_ms, to_ms=rng.to_ms, **m)


@router.get(
    "/metrics/timeseries", response_model=MetricsTimeseries, summary="Метрики по интервалам (для графиков)"
)
def get_metrics_timeseries(
    robot: Robot = Depends(get_robot_or_404),
    rng: TimeRange = Depends(get_time_range),
    bucket_s: float = Query(10.0, ge=0.1, le=3600, description="длина интервала, с"),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    points = queries.points_in_range(session, robot.id, rng.from_ms, rng.to_ms)
    buckets = compute_timeseries(
        points,
        from_ms=rng.from_ms,
        bucket_ms=int(bucket_s * 1000),
        idle_eps=settings.idle_speed_eps,
        max_gap_ms=settings.max_gap_ms,
    )
    return MetricsTimeseries(
        robot_id=robot.id, from_ms=rng.from_ms, to_ms=rng.to_ms, bucket_s=bucket_s, buckets=buckets
    )


@router.get("/events", response_model=EventsOut, summary="Потери TF, ошибки и разрывы связи")
def get_events(
    robot: Robot = Depends(get_robot_or_404),
    rng: TimeRange = Depends(get_time_range),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    points = queries.points_in_range(session, robot.id, rng.from_ms, rng.to_ms)
    events = detect_events(points, max_gap_ms=settings.max_gap_ms)
    return EventsOut(robot_id=robot.id, from_ms=rng.from_ms, to_ms=rng.to_ms, events=events)
