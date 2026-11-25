import json
import time
from pathlib import Path
import httpx

def fetch_training_data(
    base_url: str,
    robot_id: str,
    duration_s: int = 300,
    max_points: int = 10000,
    output_file: Path = Path("train_dataset.json"),
) -> None:
    to_ms = int(time.time() * 1000)
    from_ms = to_ms - duration_s * 1000

    base = base_url.rstrip("/")
    url = f"{base}/api/robots/{robot_id}/telemetry"
    params = {
        "from_ms": from_ms,
        "to_ms": to_ms,
        "max_points": max_points,
    }

    with httpx.Client(timeout=30.0) as client:
        # 1. Проверяем, какой robot_id реально зарегистрирован на бэкенде
        robots_resp = client.get(f"{base}/api/robots")
        print(f"GET /api/robots -> {robots_resp.status_code}: {robots_resp.text}")

        # 2. Запрашиваем телеметрию и выводим тело ответа при ошибке
        resp = client.get(url, params=params)
        if resp.status_code != 200:
            print(f"Ошибка {resp.status_code} на {resp.url}: {resp.text}")
        resp.raise_for_status()
        data = resp.json()

    points = data.get("points", [])
    print(f"Выгружено точек: {len(points)} из {data.get('total_in_range')} (stride={data.get('stride')})")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Сохранено в {output_file}")
