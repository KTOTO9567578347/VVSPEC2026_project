"""gRPC-сервер, который принимает батчи от ROS2-ноды grpc_bridge."""

import logging
from concurrent import futures
from typing import Any

import grpc

from app.db import Database
from app.grpc_gen import telemetry_pb2, telemetry_pb2_grpc
from app.services.ingest import ingest_batch, now_ms

log = logging.getLogger(__name__)

MAX_MESSAGE_BYTES = 32 * 1024 * 1024


def point_from_proto(p: telemetry_pb2.TelemetryPoint) -> dict[str, Any]:
    status = telemetry_pb2.TelemetryStatus.Name(p.status)
    has_pose = p.HasField("pose") and status == "OK"
    return {
        "timestamp_ms": p.timestamp_ms,
        "status": status,
        "status_message": p.status_message or None,
        "x": p.pose.x if has_pose else None,
        "y": p.pose.y if has_pose else None,
        "yaw": p.pose.yaw if has_pose else None,
        "cmd_linear_x": p.cmd_vel.linear_x,
        "cmd_angular_z": p.cmd_vel.angular_z,
        "odom_linear_x": p.odom_vel.linear_x,
        "odom_angular_z": p.odom_vel.angular_z,
    }


class TelemetryServicer(telemetry_pb2_grpc.TelemetryServiceServicer):
    def __init__(self, db: Database, hub=None):
        self.db = db
        self.hub = hub

    def SendTelemetryBatch(self, request, context):
        robot_id = request.robot_id.strip()
        if not robot_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "robot_id is required")
        if not request.points:
            return telemetry_pb2.TelemetryResponse(success=True)

        points = [point_from_proto(p) for p in request.points]
        try:
            with self.db.session() as session:
                ingest_batch(session, robot_id, points, received_at_ms=now_ms())
        except Exception:
            log.exception("Не удалось сохранить батч от %s", robot_id)
            context.abort(grpc.StatusCode.INTERNAL, "failed to store batch")

        log.debug("Принят батч от %s: %d точек", robot_id, len(points))
        if self.hub is not None:
            self.hub.publish(robot_id, points)
        return telemetry_pb2.TelemetryResponse(success=True)


def create_grpc_server(
    db: Database, hub=None, host: str = "0.0.0.0", port: int = 50051, workers: int = 8
) -> tuple[grpc.Server, int]:
    """Создаёт (но не запускает) сервер. Возвращает сервер и реально занятый порт
    (полезно при port=0 в тестах)."""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=workers),
        options=[
            ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
            ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
        ],
    )
    telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(TelemetryServicer(db, hub), server)
    bound_port = server.add_insecure_port(f"{host}:{port}")
    if bound_port == 0:
        raise RuntimeError(f"Не удалось занять gRPC-порт {host}:{port}")
    return server, bound_port
