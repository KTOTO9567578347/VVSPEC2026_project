from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_robot_or_404, get_session
from app.models import Anomaly, Robot
from app.schemas import AnomalyCreate, AnomalyOut
from app.services.anomalies import create_or_extend_anomaly, list_anomalies

router = APIRouter(tags=["anomalies"])


@router.get(
    "/api/anomalies",
    response_model=list[AnomalyOut],
    summary="Список сохранённых аномалий",
)
def get_anomalies(
    robot_id: str | None = Query(None, min_length=1),
    is_fixed: bool | None = Query(None),
    session: Session = Depends(get_session),
):
    return list_anomalies(session, robot_id=robot_id, is_fixed=is_fixed)


@router.post(
    "/api/robots/{robot_id}/anomalies",
    response_model=AnomalyOut,
    summary="Добавить аномалию или продлить активную",
)
def add_anomaly(
    payload: AnomalyCreate,
    robot: Robot = Depends(get_robot_or_404),
    session: Session = Depends(get_session),
):
    robot = session.scalar(select(Robot).where(Robot.id == robot.id).with_for_update())
    if robot is None:
        raise HTTPException(status_code=404, detail="robot not found")

    anomaly = create_or_extend_anomaly(
        session,
        robot,
        payload.type,
        payload.start_timestamp_ms,
        payload.end_timestamp_ms,
        payload.confidence,
    )
    return anomaly


@router.delete("/api/anomalies/{anomaly_id}", status_code=204, summary="Удалить аномалию")
def delete_anomaly(anomaly_id: int, session: Session = Depends(get_session)):
    anomaly = session.get(Anomaly, anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail=f"anomaly '{anomaly_id}' not found")
    session.delete(anomaly)
    return Response(status_code=204)
