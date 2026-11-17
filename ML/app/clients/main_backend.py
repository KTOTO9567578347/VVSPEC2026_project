import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class BackendApiError(RuntimeError):
    """Raised when the backend returns an error or an invalid response."""


@dataclass(frozen=True)
class Robot:
    id: str


class MainBackendClient:
    def __init__(self, base_url: str, timeout_s: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def _request(
        self,
        method: str,
        path: str,
        query: dict[str, int] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                if response.status == 204:
                    return None
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            raise BackendApiError(
                f"Backend returned HTTP {exc.code} for {method} {path}: {detail}"
            ) from exc
        except URLError as exc:
            raise BackendApiError(f"Could not reach backend for {method} {path}: {exc}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BackendApiError(f"Backend returned invalid JSON for {method} {path}") from exc

    def list_robots(self) -> list[Robot]:
        response = self._request("GET", "/api/robots")
        if not isinstance(response, list):
            raise BackendApiError("Backend /api/robots response must be a JSON array")
        robots: list[Robot] = []
        for item in response:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                raise BackendApiError("Backend returned a robot without a valid id")
            robots.append(Robot(id=item["id"]))
        return robots

    def get_telemetry(
        self, robot_id: str, from_ms: int, to_ms: int, max_points: int
    ) -> dict[str, Any]:
        encoded_robot_id = quote(robot_id, safe="")
        response = self._request(
            "GET",
            f"/api/robots/{encoded_robot_id}/telemetry",
            query={"from_ms": from_ms, "to_ms": to_ms, "max_points": max_points},
        )
        if not isinstance(response, dict) or not isinstance(response.get("points"), list):
            raise BackendApiError(f"Backend returned an invalid telemetry response for {robot_id}")
        return response

    def add_anomaly(
        self,
        robot_id: str,
        anomaly_type: str,
        start_timestamp_ms: int,
        end_timestamp_ms: int,
        confidence: float,
    ) -> dict[str, Any]:
        encoded_robot_id = quote(robot_id, safe="")
        response = self._request(
            "POST",
            f"/api/robots/{encoded_robot_id}/anomalies",
            body={
                "type": anomaly_type,
                "start_timestamp_ms": start_timestamp_ms,
                "end_timestamp_ms": end_timestamp_ms,
                "confidence": confidence,
            },
        )
        if not isinstance(response, dict) or not isinstance(response.get("id"), int):
            raise BackendApiError(f"Backend returned an invalid anomaly response for {robot_id}")
        return response