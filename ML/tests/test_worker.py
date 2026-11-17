import json
from io import BytesIO
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from app.clients.main_backend import MainBackendClient, Robot
from app.core.config import Settings
from app.main import AnalysisWorker, telemetry_to_odometries
from app.schemas.payload import AnomalyPrediction


class FakeResponse:
    status = 200

    def __init__(self, content):
        self.content = BytesIO(content)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.content.close()

    def read(self, *args):
        return self.content.read(*args)


def point(timestamp_ms, x, y, yaw, linear_x=0.2, angular_z=0.1):
    return {
        "timestamp_ms": timestamp_ms,
        "status": "OK",
        "pose": {"x": x, "y": y, "yaw": yaw},
        "odom_vel": {"linear_x": linear_x, "angular_z": angular_z},
    }


class FakeClient:
    def __init__(self, points):
        self.points = points
        self.requested_telemetry = None
        self.created_anomalies = []

    def list_robots(self):
        return [Robot("r1")]

    def get_telemetry(self, robot_id, from_ms, to_ms, max_points):
        self.requested_telemetry = (robot_id, from_ms, to_ms, max_points)
        return {"points": self.points}

    def add_anomaly(self, **payload):
        self.created_anomalies.append(payload)
        return {"id": 42, **payload}


class FakeDetector:
    def predict_with_confidence(self, data, check_idle=False):
        self.data = data
        self.check_idle = check_idle
        return AnomalyPrediction("abnormal_movement", 0.91, "anomaly")


class TelemetryConversionTests(unittest.TestCase):
    def test_maps_backend_pose_and_odometry_to_detector_shape(self):
        rows = telemetry_to_odometries([point(1000, 1, 2, 0)])

        self.assertEqual(rows[0]["timestamp"], 1000)
        self.assertEqual(rows[0]["position"], {"x": 1.0, "y": 2.0, "z": 0.0})
        self.assertAlmostEqual(rows[0]["orientation"]["z"], 0.0)
        self.assertAlmostEqual(rows[0]["orientation"]["w"], 1.0)
        self.assertEqual(rows[0]["linear_velocity"]["x"], 0.2)
        self.assertEqual(rows[0]["angular_velocity"]["z"], 0.1)

    def test_skips_points_without_pose(self):
        no_pose = {
            "timestamp_ms": 1000,
            "pose": None,
            "odom_vel": {"linear_x": 0.0, "angular_z": 0.0},
        }
        self.assertEqual(telemetry_to_odometries([no_pose]), [])


class BackendClientTests(unittest.TestCase):
    def test_posts_anomaly_using_backend_timestamp_contract(self):
        response_body = (
            b'{"id":7,"robot_id":"r 1","type":"abnormal_movement",'
            b'"start_timestamp_ms":100,"end_timestamp_ms":200,"confidence":0.9,"is_fixed":false}'
        )
        client = MainBackendClient("http://backend")
        with patch("app.clients.main_backend.urlopen", return_value=FakeResponse(response_body)) as urlopen:
            response = client.add_anomaly("r 1", "abnormal_movement", 100, 200, 0.9)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "http://backend/api/robots/r%201/anomalies")
        self.assertEqual(
            json.loads(request.data),
            {
                "type": "abnormal_movement",
                "start_timestamp_ms": 100,
                "end_timestamp_ms": 200,
                "confidence": 0.9,
            },
        )
        self.assertEqual(response["id"], 7)

    def test_requests_telemetry_with_range_and_point_limit(self):
        client = MainBackendClient("http://backend")
        with patch(
            "app.clients.main_backend.urlopen",
            return_value=FakeResponse(b'{"points":[]}'),
        ) as urlopen:
            client.get_telemetry("r1", 100, 200, 500)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(
            parse_qs(urlsplit(request.full_url).query),
            {"from_ms": ["100"], "to_ms": ["200"], "max_points": ["500"]},
        )


class AnalysisWorkerTests(unittest.TestCase):
    def test_posts_detected_anomaly_using_analyzed_timestamp_bounds(self):
        points = [point(1000 + i * 100, i, 0, 0) for i in range(5)]
        client = FakeClient(points)
        detector = FakeDetector()
        settings = Settings(
            backend_api_url="http://backend",
            poll_interval_s=30,
            analysis_window_s=60,
            max_points=50000,
            request_timeout_s=15,
            anomaly_threshold=0.6,
            check_idle=False,
            classifier_path=Path("classifier.pkl"),
        )
        worker = AnalysisWorker(client, detector, settings)

        with patch("app.main.now_ms", return_value=20000):
            worker.run_once()

        self.assertEqual(client.requested_telemetry, ("r1", 0, 20000, 50000))
        self.assertEqual(len(detector.data["odometries"]), 5)
        self.assertEqual(
            client.created_anomalies,
            [
                {
                    "robot_id": "r1",
                    "anomaly_type": "abnormal_movement",
                    "start_timestamp_ms": 1000,
                    "end_timestamp_ms": 1400,
                    "confidence": 0.91,
                }
            ],
        )

    def test_does_not_post_when_detector_returns_no_anomaly(self):
        points = [point(1000 + i * 100, i, 0, 0) for i in range(5)]
        client = FakeClient(points)

        class NoAnomalyDetector:
            def predict_with_confidence(self, data, check_idle=False):
                return None

        settings = Settings(
            backend_api_url="http://backend",
            poll_interval_s=30,
            analysis_window_s=60,
            max_points=50000,
            request_timeout_s=15,
            anomaly_threshold=0.6,
            check_idle=False,
            classifier_path=Path("classifier.pkl"),
        )
        worker = AnalysisWorker(client, NoAnomalyDetector(), settings)

        with patch("app.main.now_ms", return_value=20000):
            worker.run_once()

        self.assertEqual(client.created_anomalies, [])


if __name__ == "__main__":
    unittest.main()
