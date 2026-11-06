from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TelemetryStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OK: _ClassVar[TelemetryStatus]
    NOTF: _ClassVar[TelemetryStatus]
    ERROR: _ClassVar[TelemetryStatus]
OK: TelemetryStatus
NOTF: TelemetryStatus
ERROR: TelemetryStatus

class MotionTwist(_message.Message):
    __slots__ = ("linear_x", "angular_z")
    LINEAR_X_FIELD_NUMBER: _ClassVar[int]
    ANGULAR_Z_FIELD_NUMBER: _ClassVar[int]
    linear_x: float
    angular_z: float
    def __init__(self, linear_x: _Optional[float] = ..., angular_z: _Optional[float] = ...) -> None: ...

class RobotPose(_message.Message):
    __slots__ = ("x", "y", "yaw")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    YAW_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    yaw: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., yaw: _Optional[float] = ...) -> None: ...

class TelemetryPoint(_message.Message):
    __slots__ = ("timestamp_ms", "status", "status_message", "pose", "cmd_vel", "odom_vel")
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    POSE_FIELD_NUMBER: _ClassVar[int]
    CMD_VEL_FIELD_NUMBER: _ClassVar[int]
    ODOM_VEL_FIELD_NUMBER: _ClassVar[int]
    timestamp_ms: int
    status: TelemetryStatus
    status_message: str
    pose: RobotPose
    cmd_vel: MotionTwist
    odom_vel: MotionTwist
    def __init__(self, timestamp_ms: _Optional[int] = ..., status: _Optional[_Union[TelemetryStatus, str]] = ..., status_message: _Optional[str] = ..., pose: _Optional[_Union[RobotPose, _Mapping]] = ..., cmd_vel: _Optional[_Union[MotionTwist, _Mapping]] = ..., odom_vel: _Optional[_Union[MotionTwist, _Mapping]] = ...) -> None: ...

class TelemetryBatchRequest(_message.Message):
    __slots__ = ("robot_id", "points")
    ROBOT_ID_FIELD_NUMBER: _ClassVar[int]
    POINTS_FIELD_NUMBER: _ClassVar[int]
    robot_id: str
    points: _containers.RepeatedCompositeFieldContainer[TelemetryPoint]
    def __init__(self, robot_id: _Optional[str] = ..., points: _Optional[_Iterable[_Union[TelemetryPoint, _Mapping]]] = ...) -> None: ...

class TelemetryResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: _Optional[bool] = ...) -> None: ...
