from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Robot, TelemetryBatch, TelemetryPoint


def list_robots(session: Session) -> list[Robot]:
    return list(session.scalars(select(Robot).order_by(Robot.id)))


def get_robot(session: Session, robot_id: str) -> Robot | None:
    return session.get(Robot, robot_id)


def latest_point(session: Session, robot_id: str) -> TelemetryPoint | None:
    stmt = (
        select(TelemetryPoint)
        .where(TelemetryPoint.robot_id == robot_id)
        .order_by(TelemetryPoint.timestamp_ms.desc(), TelemetryPoint.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _range_filter(stmt, robot_id: str, from_ms: int, to_ms: int):
    return stmt.where(
        TelemetryPoint.robot_id == robot_id,
        TelemetryPoint.timestamp_ms >= from_ms,
        TelemetryPoint.timestamp_ms <= to_ms,
    )


def points_in_range(
    session: Session, robot_id: str, from_ms: int, to_ms: int, only_ok: bool = False
) -> list[TelemetryPoint]:
    stmt = _range_filter(select(TelemetryPoint), robot_id, from_ms, to_ms)
    if only_ok:
        stmt = stmt.where(TelemetryPoint.status == "OK", TelemetryPoint.x.is_not(None))
    stmt = stmt.order_by(TelemetryPoint.timestamp_ms, TelemetryPoint.id)
    return list(session.scalars(stmt))


def points_downsampled(
    session: Session, robot_id: str, from_ms: int, to_ms: int, max_points: int, only_ok: bool = False
) -> tuple[list[TelemetryPoint], int, int]:
    """Возвращает (точки, всего в диапазоне, шаг). Прореживание делается в SQL
    через row_number(), так что большие диапазоны не тянутся в память целиком."""
    base = _range_filter(select(TelemetryPoint), robot_id, from_ms, to_ms)
    count_stmt = _range_filter(select(func.count()).select_from(TelemetryPoint), robot_id, from_ms, to_ms)
    if only_ok:
        cond = (TelemetryPoint.status == "OK", TelemetryPoint.x.is_not(None))
        base = base.where(*cond)
        count_stmt = count_stmt.where(*cond)

    total = int(session.scalar(count_stmt) or 0)
    if total == 0:
        return [], 0, 1

    stride = max(1, -(-total // max_points))  # ceil
    if stride == 1:
        rows = session.scalars(base.order_by(TelemetryPoint.timestamp_ms, TelemetryPoint.id))
        return list(rows), total, 1

    rn = func.row_number().over(order_by=(TelemetryPoint.timestamp_ms, TelemetryPoint.id)).label("rn")
    numbered = base.with_only_columns(TelemetryPoint.id, rn).subquery()
    picked = select(numbered.c.id).where((numbered.c.rn - 1) % stride == 0)
    stmt = (
        select(TelemetryPoint)
        .where(TelemetryPoint.id.in_(picked))
        .order_by(TelemetryPoint.timestamp_ms, TelemetryPoint.id)
    )
    return list(session.scalars(stmt)), total, stride


def delete_robot(session: Session, robot_id: str) -> bool:
    robot = session.get(Robot, robot_id)
    if robot is None:
        return False
    session.execute(delete(TelemetryPoint).where(TelemetryPoint.robot_id == robot_id))
    session.execute(delete(TelemetryBatch).where(TelemetryBatch.robot_id == robot_id))
    session.delete(robot)
    return True
