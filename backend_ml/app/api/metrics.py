from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import TimeRange, get_robot_or_404, get_session, get_settings_dep, get_time_range
from app.config import Settings
from app.models import Robot
from app.schemas import Metrics
from app.services import queries
from app.services.metrics import compute_metrics

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
