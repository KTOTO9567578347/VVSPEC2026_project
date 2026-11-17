import time

import pytest
from sqlalchemy import select

from app.models import Anomaly
from app.services.ingest import ingest_batch, now_ms
from tests.conftest import make_point


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["database"] is True


def test_empty_robots(client):
    assert client.get("/api/robots").json() == []


def test_robot_not_found(client):
    assert client.get("/api/robots/nope").status_code == 404
    assert client.get("/api/robots/nope/metrics").status_code == 404


def test_robot_list(client, seeded):
    robots = client.get("/api/robots").json()
    assert len(robots) == 1
    r = robots[0]
    assert r["id"] == "r1"
    assert r["online"] is True
    assert r["total_points"] == 13
    assert r["total_batches"] == 1
    assert r["last_point"]["status"] == "NOTF"
    assert r["last_point"]["pose"] is None


def test_telemetry_default_window(client, seeded):
    body = client.get("/api/robots/r1/telemetry").json()
    assert body["total_in_range"] == 13
    assert body["stride"] == 1
    assert body["points"][0]["pose"] == {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ts = [p["timestamp_ms"] for p in body["points"]]
    assert ts == sorted(ts)


def test_telemetry_downsampling(client, seeded):
    body = client.get("/api/robots/r1/telemetry", params={"max_points": 5}).json()
    assert body["stride"] == 3
    assert len(body["points"]) == 5  # 13 точек, каждая третья: 0,3,6,9,12
    assert body["points"][0]["timestamp_ms"] == seeded["t0"]


def test_telemetry_range(client, seeded):
    t0 = seeded["t0"]
    body = client.get("/api/robots/r1/telemetry", params={"from_ms": t0 + 250, "to_ms": t0 + 550}).json()
    assert [p["timestamp_ms"] - t0 for p in body["points"]] == [300, 400, 500]


def test_bad_range(client, seeded):
    r = client.get("/api/robots/r1/telemetry", params={"from_ms": 10, "to_ms": 5})
    assert r.status_code == 422


def test_latest(client, seeded):
    p = client.get("/api/robots/r1/telemetry/latest").json()
    assert p["timestamp_ms"] == seeded["t_end"]


def test_trajectory_only_ok(client, seeded):
    body = client.get("/api/robots/r1/trajectory").json()
    assert len(body["points"]) == 10
    assert body["points"][-1]["x"] == pytest.approx(0.9)


def test_metrics(client, seeded):
    m = client.get("/api/robots/r1/metrics").json()
    assert m["samples"] == 13
    assert m["distance_m"] == pytest.approx(0.9)
    assert m["status_counts"] == {"OK": 10, "NOTF": 3, "ERROR": 0}
    assert m["linear_tracking"]["rmse"] == pytest.approx(0.1)


def test_timeseries(client, seeded):
    body = client.get(
        "/api/robots/r1/metrics/timeseries",
        params={"from_ms": seeded["t0"], "to_ms": seeded["t_end"], "bucket_s": 0.5},
    ).json()
    assert [b["samples"] for b in body["buckets"]] == [5, 5, 3]


def test_events(client, seeded):
    events = client.get("/api/robots/r1/events").json()["events"]
    assert len(events) == 1
    assert events[0]["type"] == "NOTF"
    assert events[0]["samples"] == 3


def test_offline_robot(client, db):
    old = now_ms() - 3_600_000
    with db.session() as s:
        ingest_batch(s, "old", [make_point(old)], received_at_ms=old)
    r = client.get("/api/robots/old").json()
    assert r["online"] is False


def test_delete_robot(client, seeded):
    assert client.delete("/api/robots/r1").status_code == 204
    assert client.get("/api/robots/r1").status_code == 404
    assert client.delete("/api/robots/r1").status_code == 404


def test_add_anomaly_extends_active_by_type(client, seeded):
    url = "/api/robots/r1/anomalies"
    first = client.post(
        url,
        json={
            "type": "OBSTACLE",
            "start_timestamp_ms": seeded["t0"] + 200,
            "end_timestamp_ms": seeded["t0"] + 400,
            "confidence": 0.7,
        },
    )
    assert first.status_code == 200
    initial = first.json()
    assert initial["is_fixed"] is False
    assert initial["start_timestamp_ms"] == seeded["t0"] + 200
    assert initial["end_timestamp_ms"] == seeded["t0"] + 400

    extended = client.post(
        url,
        json={
            "type": "OBSTACLE",
            "start_timestamp_ms": seeded["t0"] + 100,
            "end_timestamp_ms": seeded["t0"] + 600,
            "confidence": 0.9,
        },
    )
    assert extended.status_code == 200
    result = extended.json()
    assert result["id"] == initial["id"]
    assert result["start_timestamp_ms"] == seeded["t0"] + 100
    assert result["end_timestamp_ms"] == seeded["t0"] + 600
    assert result["confidence"] == pytest.approx(0.9)
    with client.app.state.db.session() as session:
        assert len(list(session.scalars(select(Anomaly)))) == 1


def test_anomaly_types_are_separate_and_delete(client, seeded):
    url = "/api/robots/r1/anomalies"
    first = client.post(
        url,
        json={
            "type": "OBSTACLE",
            "start_timestamp_ms": seeded["t0"],
            "end_timestamp_ms": seeded["t0"],
            "confidence": 0.5,
        },
    )
    second = client.post(
        url,
        json={
            "type": "LOCALIZATION",
            "start_timestamp_ms": seeded["t0"],
            "end_timestamp_ms": seeded["t0"],
            "confidence": 0.8,
        },
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]

    assert client.delete(f"/api/anomalies/{first.json()['id']}").status_code == 204
    assert client.delete(f"/api/anomalies/{first.json()['id']}").status_code == 404


def test_list_anomalies_with_filters(client, seeded):
    url = "/api/robots/r1/anomalies"
    active = client.post(
        url,
        json={
            "type": "OBSTACLE",
            "start_timestamp_ms": seeded["t0"],
            "end_timestamp_ms": seeded["t0"] + 100,
            "confidence": 0.8,
        },
    ).json()
    fixed = client.post(
        url,
        json={
            "type": "LOCALIZATION",
            "start_timestamp_ms": seeded["t0"] + 200,
            "end_timestamp_ms": seeded["t0"] + 300,
            "confidence": 0.9,
        },
    ).json()
    with client.app.state.db.session() as session:
        anomaly = session.get(Anomaly, fixed["id"])
        anomaly.is_fixed = True

    all_anomalies = client.get("/api/anomalies")
    assert all_anomalies.status_code == 200
    assert [row["id"] for row in all_anomalies.json()] == [fixed["id"], active["id"]]

    robot_anomalies = client.get("/api/anomalies", params={"robot_id": "r1"})
    assert len(robot_anomalies.json()) == 2
    active_anomalies = client.get("/api/anomalies", params={"is_fixed": "false"})
    assert [row["id"] for row in active_anomalies.json()] == [active["id"]]
    fixed_anomalies = client.get(
        "/api/anomalies", params={"robot_id": "r1", "is_fixed": "true"}
    )
    assert [row["id"] for row in fixed_anomalies.json()] == [fixed["id"]]


def test_add_anomaly_rejects_reversed_timestamp_range(client, seeded):
    response = client.post(
        "/api/robots/r1/anomalies",
        json={
            "type": "OBSTACLE",
            "start_timestamp_ms": seeded["t0"] + 100,
            "end_timestamp_ms": seeded["t0"],
            "confidence": 0.5,
        },
    )
    assert response.status_code == 422


def test_live_websocket(client, seeded):
    hub = client.app.state.hub
    with client.websocket_connect("/ws/live?robot_id=r1") as ws:
        # подписка регистрируется после accept — ждём её
        for _ in range(100):
            if hub.subscribers_count():
                break
            time.sleep(0.01)
        hub.publish("other", [make_point(1)])  # чужой робот не должен прийти
        hub.publish("r1", [make_point(42, x=1.5)])
        msg = ws.receive_json()
        assert msg["robot_id"] == "r1"
        assert msg["points"][0]["timestamp_ms"] == 42
        assert msg["points"][0]["pose"]["x"] == 1.5
