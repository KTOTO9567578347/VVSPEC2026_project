"""Расчёт метрик по точкам телеметрии.

Функции принимают последовательность объектов с атрибутами TelemetryPoint
(ORM-объекты или что угодно похожее), отсортированных по timestamp_ms.
"""

import math
from collections.abc import Sequence
from typing import Any


def _wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def _tracking(errors: Sequence[float]) -> dict[str, float]:
    if not errors:
        return {"rmse": 0.0, "mae": 0.0, "max_abs": 0.0}
    n = len(errors)
    return {
        "rmse": math.sqrt(sum(e * e for e in errors) / n),
        "mae": sum(abs(e) for e in errors) / n,
        "max_abs": max(abs(e) for e in errors),
    }


def _has_pose(p) -> bool:
    return p.status == "OK" and p.x is not None and p.y is not None


def compute_metrics(points: Sequence[Any], idle_eps: float = 0.01, max_gap_ms: int = 2000) -> dict[str, Any]:
    n = len(points)
    counts = {"OK": 0, "NOTF": 0, "ERROR": 0}
    for p in points:
        counts[p.status] = counts.get(p.status, 0) + 1

    if n == 0:
        zero = _tracking([])
        return {
            "samples": 0,
            "duration_s": 0.0,
            "status_counts": counts,
            "tf_availability": 0.0,
            "distance_m": 0.0,
            "displacement_m": 0.0,
            "path_efficiency": None,
            "total_rotation_rad": 0.0,
            "avg_speed_mps": 0.0,
            "max_speed_mps": 0.0,
            "path_speed_mps": 0.0,
            "avg_angular_speed_rps": 0.0,
            "idle_ratio": 0.0,
            "moving_ratio": 0.0,
            "linear_tracking": zero,
            "angular_tracking": zero,
            "gaps": 0,
            "gap_time_s": 0.0,
        }

    duration_s = (points[-1].timestamp_ms - points[0].timestamp_ms) / 1000.0

    # --- путь и повороты по позе ---
    distance = 0.0
    rotation = 0.0
    posed = [p for p in points if _has_pose(p)]
    for a, b in zip(posed, posed[1:]):
        if b.timestamp_ms - a.timestamp_ms > max_gap_ms:
            continue  # после долгого разрыва поза могла «прыгнуть» — не считаем
        distance += math.hypot(b.x - a.x, b.y - a.y)
        if a.yaw is not None and b.yaw is not None:
            rotation += abs(_wrap_angle(b.yaw - a.yaw))
    displacement = math.hypot(posed[-1].x - posed[0].x, posed[-1].y - posed[0].y) if len(posed) >= 2 else 0.0

    # --- разрывы в данных ---
    gaps = 0
    gap_time_ms = 0
    for a, b in zip(points, points[1:]):
        dt = b.timestamp_ms - a.timestamp_ms
        if dt > max_gap_ms:
            gaps += 1
            gap_time_ms += dt

    # --- скорости и ошибка слежения за командой ---
    speeds = [abs(p.odom_linear_x) for p in points]
    ang_speeds = [abs(p.odom_angular_z) for p in points]
    lin_err = [p.cmd_linear_x - p.odom_linear_x for p in points]
    ang_err = [p.cmd_angular_z - p.odom_angular_z for p in points]
    idle = sum(1 for p in points if abs(p.cmd_linear_x) < idle_eps and abs(p.cmd_angular_z) < idle_eps)
    moving = sum(1 for p in points if abs(p.odom_linear_x) >= idle_eps or abs(p.odom_angular_z) >= idle_eps)

    return {
        "samples": n,
        "duration_s": duration_s,
        "status_counts": counts,
        "tf_availability": counts["OK"] / n,
        "distance_m": distance,
        "displacement_m": displacement,
        "path_efficiency": (displacement / distance) if distance > 1e-9 else None,
        "total_rotation_rad": rotation,
        "avg_speed_mps": sum(speeds) / n,
        "max_speed_mps": max(speeds),
        "path_speed_mps": distance / duration_s if duration_s > 0 else 0.0,
        "avg_angular_speed_rps": sum(ang_speeds) / n,
        "idle_ratio": idle / n,
        "moving_ratio": moving / n,
        "linear_tracking": _tracking(lin_err),
        "angular_tracking": _tracking(ang_err),
        "gaps": gaps,
        "gap_time_s": gap_time_ms / 1000.0,
    }
