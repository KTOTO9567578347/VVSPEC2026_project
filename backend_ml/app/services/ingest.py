import time
from collections.abc import Sequence
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models import Robot, TelemetryBatch, TelemetryPoint

STATUSES = ("OK", "NOTF", "ERROR")

POINT_FIELDS = (
    "timestamp_ms",
    "status",
    "status_message",
    "x",
    "y",
    "yaw",
    "cmd_linear_x",
    "cmd_angular_z",
    "odom_linear_x",
    "odom_angular_z",
)


def now_ms() -> int:
    return int(time.time() * 1000)


def ingest_batch(
    session: Session,
    robot_id: str,
    points: Sequence[dict[str, Any]],
    received_at_ms: int | None = None,
) -> Robot:
    """Сохраняет батч точек одного робота. Точки — словари с ключами POINT_FIELDS."""
    if not robot_id:
        raise ValueError("robot_id is required")
    if not points:
        raise ValueError("batch is empty")

    received_at_ms = received_at_ms if received_at_ms is not None else now_ms()
    timestamps = [int(p["timestamp_ms"]) for p in points]
    first_ts, last_ts = min(timestamps), max(timestamps)

    robot = session.get(Robot, robot_id, with_for_update=True)
    if robot is None:
        robot = Robot(
            id=robot_id,
            first_seen_ms=received_at_ms,
            last_seen_ms=received_at_ms,
            last_point_ms=last_ts,
            total_points=0,
            total_batches=0,
        )
        session.add(robot)
        session.flush()

    robot.last_seen_ms = max(robot.last_seen_ms, received_at_ms)
    robot.last_point_ms = max(robot.last_point_ms or last_ts, last_ts)
    robot.total_points += len(points)
    robot.total_batches += 1

    rows = []
    for p in points:
        row = {field: p.get(field) for field in POINT_FIELDS}
        row["robot_id"] = robot_id
        row["timestamp_ms"] = int(row["timestamp_ms"])
        if row["status"] not in STATUSES:
            row["status"] = "ERROR"
        for f in ("cmd_linear_x", "cmd_angular_z", "odom_linear_x", "odom_angular_z"):
            row[f] = float(row[f] or 0.0)
        rows.append(row)
    session.execute(insert(TelemetryPoint), rows)

    session.add(
        TelemetryBatch(
            robot_id=robot_id,
            received_at_ms=received_at_ms,
            points_count=len(points),
            first_point_ms=first_ts,
            last_point_ms=last_ts,
        )
    )
    return robot
