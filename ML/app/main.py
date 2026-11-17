import logging
import math
import signal
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from app.clients.main_backend import MainBackendClient, Robot
from app.core.config import Settings, load_settings
from app.schemas.payload import AnomalyPrediction

log = logging.getLogger("ml_worker")
MIN_ANALYSIS_POINTS = 5


class Detector(Protocol):
    def predict_with_confidence(
        self, data_dict: dict, check_idle: bool = False
    ) -> AnomalyPrediction | None: ...


def now_ms() -> int:
    return int(time.time() * 1000)


def telemetry_to_odometries(points: list[dict]) -> list[dict]:
    odometries = []
    for point in points:
        timestamp_ms = point.get("timestamp_ms")
        pose = point.get("pose")
        odom_vel = point.get("odom_vel")
        if not isinstance(timestamp_ms, int) or not isinstance(odom_vel, dict):
            raise ValueError("Telemetry point is missing timestamp_ms or odom_vel")
        if pose is None:
            continue
        if not isinstance(pose, dict):
            raise ValueError("Telemetry pose must be an object or null")

        x, y, yaw = pose.get("x"), pose.get("y"), pose.get("yaw")
        linear_x, angular_z = odom_vel.get("linear_x"), odom_vel.get("angular_z")
        values = (x, y, yaw, linear_x, angular_z)
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
            raise ValueError("Telemetry pose and odometry values must be finite numbers")

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
                "linear_velocity": {"x": float(linear_x), "y": 0.0, "z": 0.0},
                "angular_velocity": {"x": 0.0, "y": 0.0, "z": float(angular_z)},
            }
        )
    return odometries


@dataclass
class RobotAnalysis:
    prediction: AnomalyPrediction
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
        odometries = telemetry_to_odometries(export["points"])
        if len(odometries) < MIN_ANALYSIS_POINTS:
            log.info(
                "Skipping robot %s: only %d pose points in analysis window",
                robot.id,
                len(odometries),
            )
            return None

        prediction = self.detector.predict_with_confidence(
            {"odometries": odometries},
            check_idle=self.settings.check_idle,
        )
        if prediction is None:
            return None
        return RobotAnalysis(
            prediction=prediction,
            start_timestamp_ms=odometries[0]["timestamp"],
            end_timestamp_ms=odometries[-1]["timestamp"],
        )

    def run_once(self) -> None:
        to_ms = now_ms()
        for robot in self.client.list_robots():
            try:
                prediction = self.analyze_robot(robot, to_ms)
                if prediction is None:
                    continue
                result = prediction.prediction
                anomaly = self.client.add_anomaly(
                    robot_id=robot.id,
                    anomaly_type=result.anomaly_type,
                    start_timestamp_ms=prediction.start_timestamp_ms,
                    end_timestamp_ms=prediction.end_timestamp_ms,
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
    detector = AnomalyDetector(
        model_path=settings.classifier_path,
        threshold=settings.anomaly_threshold,
    )
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
