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


class TrackingError(BaseModel):
    rmse: float
    mae: float
    max_abs: float


class Metrics(BaseModel):
    robot_id: str
    from_ms: int
    to_ms: int
    samples: int
    duration_s: float
    status_counts: dict[str, int]
    tf_availability: float = Field(description="доля точек со статусом OK, 0..1")
    distance_m: float = Field(description="пройденный путь по позе")
    displacement_m: float = Field(description="расстояние между первой и последней позой")
    path_efficiency: float | None = Field(description="displacement / distance")
    total_rotation_rad: float
    avg_speed_mps: float = Field(description="средняя |odom.linear_x|")
    max_speed_mps: float
    path_speed_mps: float = Field(description="distance / duration")
    avg_angular_speed_rps: float
    idle_ratio: float = Field(description="доля времени, когда команда на движение нулевая")
    moving_ratio: float = Field(description="доля времени, когда робот реально движется")
    linear_tracking: TrackingError = Field(description="ошибка cmd_vel.linear_x - odom_vel.linear_x")
    angular_tracking: TrackingError = Field(description="ошибка cmd_vel.angular_z - odom_vel.angular_z")
    gaps: int = Field(description="сколько раз данные пропадали дольше max_gap_ms")
    gap_time_s: float


class MetricsBucket(BaseModel):
    t: int = Field(description="начало интервала, мс")
    samples: int
    tf_availability: float
    distance_m: float
    avg_speed_mps: float
    avg_cmd_speed_mps: float
    avg_angular_speed_rps: float
    linear_rmse: float
    angular_rmse: float


class MetricsTimeseries(BaseModel):
    robot_id: str
    from_ms: int
    to_ms: int
    bucket_s: float
    buckets: list[MetricsBucket]


class Event(BaseModel):
    type: Literal["NOTF", "ERROR", "GAP"]
    start_ms: int
    end_ms: int
    duration_s: float
    samples: int
    message: str | None = None


class EventsOut(BaseModel):
    robot_id: str
    from_ms: int
    to_ms: int
    events: list[Event]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    grpc_port: int | None
    version: str
