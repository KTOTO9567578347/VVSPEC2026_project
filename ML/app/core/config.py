import math
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    backend_api_url: str
    poll_interval_s: float
    analysis_window_s: int
    max_points: int
    request_timeout_s: float
    anomaly_threshold: float
    check_idle: bool
    classifier_path: Path


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def load_settings() -> Settings:
    backend_api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")
    if not backend_api_url.startswith(("http://", "https://")):
        raise ValueError("BACKEND_API_URL must start with http:// or https://")

    try:
        analysis_window_s = int(os.getenv("ANALYSIS_WINDOW_S", "600"))
        max_points = int(os.getenv("MAX_POINTS", "50000"))
        anomaly_threshold = float(os.getenv("ANOMALY_THRESHOLD", "0.6"))
    except ValueError as exc:
        raise ValueError("ANALYSIS_WINDOW_S, MAX_POINTS, and ANOMALY_THRESHOLD must be numeric") from exc

    if analysis_window_s <= 0:
        raise ValueError("ANALYSIS_WINDOW_S must be positive")
    if not 1 <= max_points <= 50000:
        raise ValueError("MAX_POINTS must be between 1 and 50000")
    if not 0 <= anomaly_threshold <= 1:
        raise ValueError("ANOMALY_THRESHOLD must be between 0 and 1")

    raw_check_idle = os.getenv("CHECK_IDLE", "false").lower()
    if raw_check_idle not in {"true", "false"}:
        raise ValueError("CHECK_IDLE must be true or false")

    classifier_path = Path(
        os.getenv(
            "CLASSIFIER_PATH",
            str(Path(__file__).resolve().parents[1] / "services" / "classifier.pkl"),
        )
    )
    return Settings(
        backend_api_url=backend_api_url,
        poll_interval_s=_positive_float("POLL_INTERVAL_S", 30.0),
        analysis_window_s=analysis_window_s,
        max_points=max_points,
        request_timeout_s=_positive_float("REQUEST_TIMEOUT_S", 15.0),
        anomaly_threshold=anomaly_threshold,
        check_idle=raw_check_idle == "true",
        classifier_path=classifier_path,
    )