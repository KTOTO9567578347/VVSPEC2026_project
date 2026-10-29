from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["OK", "NOTF", "ERROR"]


class Pose(BaseModel):
    x: float
    y: float
    yaw: float


class Twist(BaseModel):
    linear_x: float
    angular_z: float


class PointOut(BaseModel):
    timestamp_ms: int
    status: Status
    status_message: str | None = None
    pose: Pose | None = None
    cmd_vel: Twist
    odom_vel: Twist

    @classmethod
    def from_row(cls, r) -> "PointOut":
        """r — ORM-объект TelemetryPoint или словарь с теми же полями."""
        get = r.get if isinstance(r, dict) else lambda k: getattr(r, k)
        x, y, yaw = get("x"), get("y"), get("yaw")
        return cls(
            timestamp_ms=get("timestamp_ms"),
            status=get("status"),
            status_message=get("status_message"),
            pose=Pose(x=x, y=y, yaw=yaw) if x is not None and y is not None else None,
            cmd_vel=Twist(linear_x=get("cmd_linear_x"), angular_z=get("cmd_angular_z")),
            odom_vel=Twist(linear_x=get("odom_linear_x"), angular_z=get("odom_angular_z")),
        )


class RobotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    online: bool
    first_seen_ms: int
    last_seen_ms: int
    last_point_ms: int | None
    total_points: int
    total_batches: int
    last_point: PointOut | None = None


class TelemetryPage(BaseModel):
    robot_id: str
    from_ms: int
    to_ms: int
    total_in_range: int = Field(description="сколько точек в диапазоне всего")
    stride: int = Field(description="каждая N-я точка (прореживание до max_points)")
    points: list[PointOut]


class TrajectoryPoint(BaseModel):
    t: int
    x: float
    y: float
    yaw: float


class Trajectory(BaseModel):
    robot_id: str
    from_ms: int
    to_ms: int
    points: list[TrajectoryPoint]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    grpc_port: int | None
    version: str
