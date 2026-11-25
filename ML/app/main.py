import logging
import math
import signal
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.clients.main_backend import MainBackendClient, Robot
from app.core.config import Settings, load_settings
from app.schemas.payload import AnomalyPrediction

log = logging.getLogger("ml_worker")
MIN_ANALYSIS_POINTS = 5


class Detector(Protocol):
    def analyze(
        self, data_dict: dict, check_idle: bool = False
    ) -> tuple[dict[str, float], AnomalyPrediction | None]: ...

    def predict_with_confidence(
        self, data_dict: dict, check_idle: bool = False
    ) -> AnomalyPrediction | None: ...


def now_ms() -> int:
    return int(time.time() * 1000)


def parse_telemetry_points(points: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Синхронно извлекает списки odometries и cmd_vels из точек экспорта бэкенда.
    """
    odometries = []
    cmd_vels = []

    for point in points:
        timestamp_ms = point.get("timestamp_ms")
        pose = point.get("pose")
        odom_vel = point.get("odom_vel")
        cmd_vel = point.get("cmd_vel")  # Ожидаем объект {"linear_x": ..., "angular_z": ...}

        if not isinstance(timestamp_ms, int) or not isinstance(odom_vel, dict):
            raise ValueError("Telemetry point is missing timestamp_ms or odom_vel")
        if pose is None:
            continue
        if not isinstance(pose, dict):
            raise ValueError("Telemetry pose must be an object or null")

        x, y, yaw = pose.get("x"), pose.get("y"), pose.get("yaw")
        odom_lin, odom_ang = odom_vel.get("linear_x"), odom_vel.get("angular_z")
        odom_values = (x, y, yaw, odom_lin, odom_ang)
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in odom_values):
            raise ValueError("Telemetry pose and odometry values must be finite numbers")

        # Если cmd_vel в конкретной точке отсутствует (null), подставляем нули
        if isinstance(cmd_vel, dict):
            cmd_lin = cmd_vel.get("linear_x", 0.0)
            cmd_ang = cmd_vel.get("angular_z", 0.0)
        else:
            cmd_lin, cmd_ang = 0.0, 0.0

        if not isinstance(cmd_lin, (int, float)) or not math.isfinite(cmd_lin):
            cmd_lin = 0.0
        if not isinstance(cmd_ang, (int, float)) or not math.isfinite(cmd_ang):
            cmd_ang = 0.0

        odometries.append(
            {
                "frame_id": "odom",
                "timestamp": timestamp_ms,
                "position": {"x": float(x), "y": float(y), "z": 0.0},
                "orientation": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": math.sin(float(yaw) / 2),
                    "w": math.cos(float(yaw) / 2),
                },
                "linear_velocity": {"x": float(odom_lin), "y": 0.0, "z": 0.0},
                "angular_velocity": {"x": 0.0, "y": 0.0, "z": float(odom_ang)},
            }
        )

        cmd_vels.append(
            {
                "timestamp": timestamp_ms,
                "linear": {"x": float(cmd_lin), "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": float(cmd_ang)},
            }
        )

    return odometries, cmd_vels


@dataclass
class RobotAnalysis:
    prediction: AnomalyPrediction
    metrics: dict[str, float]
    start_timestamp_ms: int
    end_timestamp_ms: int


@dataclass
class AnalysisWorker:
    client: MainBackendClient
    detector: Detector
    settings: Settings

    def analyze_robot(self, robot: Robot, to_ms: int) -> RobotAnalysis | None:
        from_ms = max(0, to_ms - self.settings.analysis_window_s * 1000)
        export = self.client.get_telemetry(
            robot.id,
            from_ms=from_ms,
            to_ms=to_ms,
            max_points=self.settings.max_points,
        )
        odometries, cmd_vels = parse_telemetry_points(export["points"])

        if len(odometries) < MIN_ANALYSIS_POINTS:
            log.info(
                "Skipping robot %s: only %d pose points in analysis window",
                robot.id,
                len(odometries),
            )
            return None

        metrics, prediction = self.detector.analyze(
            {
                "robot_id": robot.id,
                "odometries": odometries,
                "cmd_vels": cmd_vels,
            },
            check_idle=self.settings.check_idle,
        )

        log.debug("Robot %s tracking metrics: %s", robot.id, metrics)

        if prediction is None:
            return None

        return RobotAnalysis(
            prediction=prediction,
            metrics=metrics,
            start_timestamp_ms=odometries[0]["timestamp"],
            end_timestamp_ms=odometries[-1]["timestamp"],
        )

    def run_once(self) -> None:
        to_ms = now_ms()
        for robot in self.client.list_robots():
            try:
                analysis = self.analyze_robot(robot, to_ms)
                if analysis is None:
                    continue
                result = analysis.prediction
                anomaly = self.client.add_anomaly(
                    robot_id=robot.id,
                    anomaly_type=result.anomaly_type,
                    start_timestamp_ms=analysis.start_timestamp_ms,
                    end_timestamp_ms=analysis.end_timestamp_ms,
                    confidence=result.confidence,
                )
                log.info(
                    "Anomaly %s for robot %s: confidence=%.3f, interval=%d..%d",
                    anomaly["id"],
                    robot.id,
                    result.confidence,
                    anomaly["start_timestamp_ms"],
                    anomaly["end_timestamp_ms"],
                )
            except Exception:
                log.exception("Failed to analyze robot %s", robot.id)

    def run_forever(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            cycle_start = time.monotonic()
            try:
                self.run_once()
            except Exception:
                log.exception("Failed to fetch robot list or run analysis cycle")
            remaining = self.settings.poll_interval_s - (time.monotonic() - cycle_start)
            if remaining > 0 and stop_event.wait(remaining):
                break


def main() -> None:
    from app.services.anomaly_detector import AnomalyDetector

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()

    # Берем директорию, где лежат файлы моделей (на основе пути из конфига)
    models_dir = Path(settings.classifier_path).parent if settings.classifier_path else None
    detector = AnomalyDetector(models_dir=models_dir)

    client = MainBackendClient(
        base_url=settings.backend_api_url,
        timeout_s=settings.request_timeout_s,
    )
    worker = AnalysisWorker(client=client, detector=detector, settings=settings)
    stop_event = threading.Event()

    def request_stop(*signal_args: object) -> None:
        stop_event.set()
        log.info("Shutdown requested by signal %s", signal_args[0] if signal_args else "unknown")

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    log.info(
        "ML worker started: backend=%s, interval=%ss, window=%ss",
        settings.backend_api_url,
        settings.poll_interval_s,
        settings.analysis_window_s,
    )
    worker.run_forever(stop_event)


if __name__ == "__main__":
    main()
