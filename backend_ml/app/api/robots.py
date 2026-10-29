from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_robot_or_404, get_session, get_settings_dep, is_online
from app.config import Settings
from app.models import Robot
from app.schemas import PointOut, RobotOut
from app.services import queries

router = APIRouter(prefix="/api/robots", tags=["robots"])


def _robot_out(session: Session, robot: Robot, settings: Settings) -> RobotOut:
    last = queries.latest_point(session, robot.id)
    return RobotOut(
        id=robot.id,
        online=is_online(robot, settings),
        first_seen_ms=robot.first_seen_ms,
        last_seen_ms=robot.last_seen_ms,
        last_point_ms=robot.last_point_ms,
        total_points=robot.total_points,
        total_batches=robot.total_batches,
        last_point=PointOut.from_row(last) if last else None,
    )


@router.get("", response_model=list[RobotOut], summary="Список роботов с последней точкой")
def list_robots(session: Session = Depends(get_session), settings: Settings = Depends(get_settings_dep)):
    return [_robot_out(session, r, settings) for r in queries.list_robots(session)]


@router.get("/{robot_id}", response_model=RobotOut, summary="Информация о роботе")
def get_robot(
    robot: Robot = Depends(get_robot_or_404),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    return _robot_out(session, robot, settings)


@router.delete("/{robot_id}", status_code=204, summary="Удалить робота и всю его телеметрию")
def delete_robot(robot_id: str, session: Session = Depends(get_session)):
    if not queries.delete_robot(session, robot_id):
        raise HTTPException(status_code=404, detail=f"robot '{robot_id}' not found")
    return Response(status_code=204)
