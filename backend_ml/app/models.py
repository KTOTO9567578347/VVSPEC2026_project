from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# В SQLite автоинкремент работает только для INTEGER PRIMARY KEY
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class Robot(Base):
    __tablename__ = "robots"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # серверное время первого/последнего полученного батча, мс
    first_seen_ms: Mapped[int] = mapped_column(BigInteger)
    last_seen_ms: Mapped[int] = mapped_column(BigInteger)
    # время самой свежей точки по часам робота, мс
    last_point_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_points: Mapped[int] = mapped_column(BigInteger, default=0)
    total_batches: Mapped[int] = mapped_column(BigInteger, default=0)


class TelemetryBatch(Base):
    """Журнал полученных батчей — нужен для метрик доставки."""

    __tablename__ = "telemetry_batches"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    robot_id: Mapped[str] = mapped_column(ForeignKey("robots.id", ondelete="CASCADE"))
    received_at_ms: Mapped[int] = mapped_column(BigInteger)
    points_count: Mapped[int] = mapped_column(Integer)
    first_point_ms: Mapped[int] = mapped_column(BigInteger)
    last_point_ms: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_batches_robot_received", "robot_id", "received_at_ms"),)


class TelemetryPoint(Base):
    """Одна точка телеметрии (TelemetryPoint из telemetry.proto)."""

    __tablename__ = "telemetry_points"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    robot_id: Mapped[str] = mapped_column(ForeignKey("robots.id", ondelete="CASCADE"))
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)

    # OK / NOTF / ERROR
    status: Mapped[str] = mapped_column(String(8))
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # поза есть только при status == OK (иначе TF не нашёлся)
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)
    yaw: Mapped[float | None] = mapped_column(Float, nullable=True)

    cmd_linear_x: Mapped[float] = mapped_column(Float, default=0.0)
    cmd_angular_z: Mapped[float] = mapped_column(Float, default=0.0)
    odom_linear_x: Mapped[float] = mapped_column(Float, default=0.0)
    odom_angular_z: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (Index("ix_points_robot_ts", "robot_id", "timestamp_ms"),)
