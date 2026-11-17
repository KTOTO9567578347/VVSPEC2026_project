# ML telemetry analysis worker

The worker periodically reads robot IDs and telemetry from `backend_ml`, runs
the bundled `AnomalyDetector`/`classifier.pkl`, and posts detected anomalies
back to the backend. The backend merges repeated active anomalies for the same
robot and type.

## Run locally

Install the existing ML dependencies in your chosen virtual environment, then:

```bash
cd ML
python -m app
```

By default, the backend is expected at `http://localhost:8000`.

## Configuration

| Environment variable | Default | Description |
|---|---:|---|
| `BACKEND_API_URL` | `http://localhost:8000` | Base URL of `backend_ml` |
| `POLL_INTERVAL_S` | `30` | Delay between polling cycles |
| `ANALYSIS_WINDOW_S` | `600` | Recent telemetry window analyzed per robot |
| `MAX_POINTS` | `50000` | Maximum points requested per robot (backend limit: 50000) |
| `REQUEST_TIMEOUT_S` | `15` | Timeout for each backend HTTP request |
| `ANOMALY_THRESHOLD` | `0.6` | Positive-class probability threshold |
| `CHECK_IDLE` | `false` | Also report a robot that is not moving |
| `CLASSIFIER_PATH` | `app/services/classifier.pkl` | Path to the serialized classifier |

The worker reads `GET /api/robots`, then requests
`GET /api/robots/{robot_id}/telemetry` with `from_ms`, `to_ms`, and
`max_points`. It analyzes points that have a pose; points without one (such as
`NOTF`) are excluded because the detector calculates trajectory features.
At least five pose points are required for an analysis.

Detected records are sent to
`POST /api/robots/{robot_id}/anomalies` with the detector's type, the first and
last analyzed telemetry timestamps in milliseconds, and the classifier
probability. The classifier currently returns a binary anomaly score, so its
types are `abnormal_movement` and, when `CHECK_IDLE=true`, `route_not_found`.

## Docker Compose

To run only the ML worker in a separate Compose project, start the backend first
so it is available on host port `8000`, then run:

```bash
cd ML
docker compose up -d --build
docker compose logs -f ml-worker
```

By default the worker connects to `http://host.docker.internal:8000`. Set
`BACKEND_API_URL` if the backend is available at another address.

The `backend_ml/docker-compose.yaml` includes the worker and connects it to the
backend over the Compose network:

```bash
cd backend_ml
docker compose up -d --build
docker compose logs -f ml-worker
```

Override standalone Compose settings with `POLL_INTERVAL_S`,
`ANALYSIS_WINDOW_S`, `MAX_POINTS`, `REQUEST_TIMEOUT_S`, `ANOMALY_THRESHOLD`,
and `CHECK_IDLE`. The integrated `backend_ml/docker-compose.yaml` uses the
corresponding `ML_`-prefixed variables.
