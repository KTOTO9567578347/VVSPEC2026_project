from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import TimeRange, get_robot_or_404, get_session, get_time_range
from app.models import Robot
from app.schemas import PointOut, TelemetryPage, Trajectory, TrajectoryPoint
from app.services import queries

router = APIRouter(prefix="/api/robots/{robot_id}", tags=["telemetry"])


@router.get("/telemetry", response_model=TelemetryPage, summary="Сырая телеметрия за диапазон")
def get_telemetry(
    robot: Robot = Depends(get_robot_or_404),
    rng: TimeRange = Depends(get_time_range),
    max_points: int = Query(2000, ge=1, le=50000, description="если точек больше — прореживаем"),
    session: Session = Depends(get_session),
):
    rows, total, stride = queries.points_downsampled(session, robot.id, rng.from_ms, rng.to_ms, max_points)
    return TelemetryPage(
        robot_id=robot.id,
        from_ms=rng.from_ms,
        to_ms=rng.to_ms,
        total_in_range=total,
        stride=stride,
        points=[PointOut.from_row(r) for r in rows],
    )


@router.get("/telemetry/latest", response_model=PointOut, summary="Последняя точка")
def get_latest(robot: Robot = Depends(get_robot_or_404), session: Session = Depends(get_session)):
    point = queries.latest_point(session, robot.id)
    if point is None:
        raise HTTPException(status_code=404, detail="no telemetry yet")
    return PointOut.from_row(point)


@router.get("/trajectory", response_model=Trajectory, summary="Траектория (только точки с позой)")
def get_trajectory(
    robot: Robot = Depends(get_robot_or_404),
    rng: TimeRange = Depends(get_time_range),
    max_points: int = Query(5000, ge=2, le=50000),
    session: Session = Depends(get_session),
):
    rows, _, _ = queries.points_downsampled(
        session, robot.id, rng.from_ms, rng.to_ms, max_points, only_ok=True
    )
    return Trajectory(
        robot_id=robot.id,
        from_ms=rng.from_ms,
        to_ms=rng.to_ms,
        points=[TrajectoryPoint(t=r.timestamp_ms, x=r.x, y=r.y, yaw=r.yaw) for r in rows],
    )
