import math
from types import SimpleNamespace

import pytest

from app.services.metrics import compute_metrics, compute_timeseries, detect_events
from tests.conftest import make_point


def P(**kw):
    return SimpleNamespace(**make_point(**kw))


def test_empty():
    m = compute_metrics([])
    assert m["samples"] == 0
    assert m["path_efficiency"] is None


def test_straight_line():
    pts = [P(ts=i * 100, x=i * 0.1, cmd=(1.0, 0.0), odom=(0.9, 0.0)) for i in range(11)]
    m = compute_metrics(pts)
    assert m["samples"] == 11
    assert m["duration_s"] == pytest.approx(1.0)
    assert m["distance_m"] == pytest.approx(1.0)
    assert m["displacement_m"] == pytest.approx(1.0)
    assert m["path_efficiency"] == pytest.approx(1.0)
    assert m["path_speed_mps"] == pytest.approx(1.0)
    assert m["avg_speed_mps"] == pytest.approx(0.9)
    assert m["linear_tracking"]["rmse"] == pytest.approx(0.1)
    assert m["linear_tracking"]["mae"] == pytest.approx(0.1)
    assert m["tf_availability"] == 1.0
    assert m["idle_ratio"] == 0.0
    assert m["moving_ratio"] == 1.0


def test_rotation_wraps_around_pi():
    pts = [P(ts=0, yaw=math.pi - 0.1), P(ts=100, yaw=-math.pi + 0.1)]
    m = compute_metrics(pts)
    assert m["total_rotation_rad"] == pytest.approx(0.2)


def test_gap_is_not_counted_as_distance():
    pts = [P(ts=0, x=0), P(ts=100, x=0.1), P(ts=10_000, x=5.0), P(ts=10_100, x=5.1)]
    m = compute_metrics(pts, max_gap_ms=2000)
    assert m["distance_m"] == pytest.approx(0.2)
    assert m["gaps"] == 1
    assert m["gap_time_s"] == pytest.approx(9.9)


def test_idle_and_status_counts():
    pts = [P(ts=0), P(ts=100), P(ts=200, status="NOTF"), P(ts=300, status="ERROR", cmd=(0.5, 0))]
    m = compute_metrics(pts)
    assert m["status_counts"] == {"OK": 2, "NOTF": 1, "ERROR": 1}
    assert m["tf_availability"] == 0.5
    assert m["idle_ratio"] == 0.75


def test_timeseries_buckets():
    pts = [P(ts=i * 100, x=i * 0.1, odom=(1.0, 0)) for i in range(30)]  # 3 секунды
    buckets = compute_timeseries(pts, from_ms=0, bucket_ms=1000)
    assert [b["t"] for b in buckets] == [0, 1000, 2000]
    assert all(b["samples"] == 10 for b in buckets)
    assert buckets[0]["avg_speed_mps"] == pytest.approx(1.0)


def test_events():
    pts = [
        P(ts=0),
        P(ts=100, status="NOTF", msg="no tf"),
        P(ts=200, status="NOTF", msg="no tf"),
        P(ts=300),
        P(ts=5000),  # разрыв
        P(ts=5100, status="ERROR", msg="boom"),
    ]
    events = detect_events(pts, max_gap_ms=2000)
    assert [e["type"] for e in events] == ["NOTF", "GAP", "ERROR"]
    notf = events[0]
    assert (notf["start_ms"], notf["end_ms"], notf["samples"]) == (100, 200, 2)
    assert notf["message"] == "no tf"
    assert events[1]["duration_s"] == pytest.approx(4.7)
