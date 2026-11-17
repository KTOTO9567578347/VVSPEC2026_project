from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Anomaly, Robot


def list_anomalies(
    session: Session,
    robot_id: str | None = None,
    is_fixed: bool | None = None,
) -> list[Anomaly]:
    stmt = select(Anomaly)
    if robot_id is not None:
        stmt = stmt.where(Anomaly.robot_id == robot_id)
    if is_fixed is not None:
        stmt = stmt.where(Anomaly.is_fixed.is_(is_fixed))
    stmt = stmt.order_by(Anomaly.start_timestamp_ms.desc(), Anomaly.id.desc())
    return list(session.scalars(stmt))


def create_or_extend_anomaly(
    session: Session,
    robot: Robot,
    anomaly_type: str,
    start_timestamp_ms: int,
    end_timestamp_ms: int,
    confidence: float,
) -> Anomaly:

    active = session.scalar(
        select(Anomaly)
        .where(
            Anomaly.robot_id == robot.id,
            Anomaly.anomaly_type == anomaly_type,
            Anomaly.is_fixed.is_(False),
        )
        .with_for_update()
    )
    if active is None:
        active = Anomaly(
            robot_id=robot.id,
            anomaly_type=anomaly_type,
            start_timestamp_ms=start_timestamp_ms,
            end_timestamp_ms=end_timestamp_ms,
            confidence=confidence,
            is_fixed=False,
        )
        session.add(active)
        return active

    active.start_timestamp_ms = min(active.start_timestamp_ms, start_timestamp_ms)
    active.end_timestamp_ms = max(active.end_timestamp_ms, end_timestamp_ms)
    active.confidence = confidence
    return active
