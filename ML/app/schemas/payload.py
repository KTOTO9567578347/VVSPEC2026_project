from dataclasses import dataclass


@dataclass(frozen=True)
class AnomalyPrediction:
    anomaly_type: str
    confidence: float
    message: str