"""Сквозной тест: реальный gRPC-клиент (как нода grpc_bridge) → сервер → БД → REST."""

import grpc
import pytest
from fastapi.testclient import TestClient

from app.grpc_gen import telemetry_pb2 as pb
from app.grpc_gen import telemetry_pb2_grpc as pb_grpc
from app.grpc_server import create_grpc_server, point_from_proto
from app.main import create_app
from app.services.ingest import now_ms


@pytest.fixture
def grpc_stub(db):
    server, port = create_grpc_server(db, host="127.0.0.1", port=0, workers=2)
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    yield pb_grpc.TelemetryServiceStub(channel)
    channel.close()
    server.stop(0)


def _batch(robot_id, t0, n=5):
    points = []
    for i in range(n):
        p = pb.TelemetryPoint(
            timestamp_ms=t0 + i * 50,
            status=pb.OK,
            cmd_vel=pb.MotionTwist(linear_x=0.2, angular_z=0.1),
            odom_vel=pb.MotionTwist(linear_x=0.19, angular_z=0.1),
        )
        p.pose.CopyFrom(pb.RobotPose(x=i * 0.01, y=0.0, yaw=0.0))
        points.append(p)
    # точка без TF — как в ноде: pose не заполнена
    points.append(pb.TelemetryPoint(timestamp_ms=t0 + n * 50, status=pb.NOTF, status_message="no map frame"))
    return pb.TelemetryBatchRequest(robot_id=robot_id, points=points)


def test_point_from_proto_without_pose():
    p = point_from_proto(pb.TelemetryPoint(timestamp_ms=1, status=pb.NOTF, status_message="x"))
    assert p["status"] == "NOTF"
    assert p["x"] is None and p["status_message"] == "x"


def test_send_batch_and_read_via_api(settings, db, grpc_stub):
    t0 = now_ms() - 1000
    resp = grpc_stub.SendTelemetryBatch(_batch("robot_v1_simulation", t0))
    assert resp.success is True
    resp = grpc_stub.SendTelemetryBatch(_batch("robot_v1_simulation", t0 + 400))
    assert resp.success is True

    app = create_app(settings=settings, db=db, start_grpc=False)
    with TestClient(app) as c:
        robot = c.get("/api/robots/robot_v1_simulation").json()
        assert robot["total_points"] == 12
        assert robot["total_batches"] == 2
        body = c.get("/api/robots/robot_v1_simulation/telemetry").json()
        statuses = [p["status"] for p in body["points"]]
        assert statuses.count("NOTF") == 2
        notf = next(p for p in body["points"] if p["status"] == "NOTF")
        assert notf["pose"] is None
        assert notf["status_message"] == "no map frame"


def test_empty_robot_id_rejected(grpc_stub):
    with pytest.raises(grpc.RpcError) as e:
        grpc_stub.SendTelemetryBatch(_batch("", now_ms()))
    assert e.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_empty_batch_ok(grpc_stub):
    assert grpc_stub.SendTelemetryBatch(pb.TelemetryBatchRequest(robot_id="r")).success is True
