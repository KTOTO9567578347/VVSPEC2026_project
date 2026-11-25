import json
from pathlib import Path
import pandas as pd


def load_telemetry_dataframe(json_path: Path = Path("train_dataset.json")) -> pd.DataFrame:
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    rows = []
    for p in payload.get("points", []):
        pose = p.get("pose") or {}
        cmd = p.get("cmd_vel") or {}
        odom = p.get("odom_vel") or {}

        rows.append(
            {
                "timestamp_ms": p.get("timestamp_ms"),
                "status": p.get("status"),
                "x": pose.get("x"),
                "y": pose.get("y"),
                "yaw": pose.get("yaw"),
                "cmd_v": cmd.get("linear_x"),
                "cmd_w": cmd.get("angular_z"),
                "odom_v": odom.get("linear_x"),
                "odom_w": odom.get("angular_z"),
            }
        )

    df = pd.DataFrame(rows)

    # Убираем строки с пропусками, если попадались битые пакеты, и сортируем по времени
    df = df.dropna(subset=["cmd_v", "cmd_w", "odom_v", "odom_w"]).sort_values("timestamp_ms").reset_index(drop=True)

    # Добавляем лаги (фактическая скорость на прошлом шаге t-1) для признаков Модели 1
    df["prev_odom_v"] = df["odom_v"].shift(1)
    df["prev_odom_w"] = df["odom_w"].shift(1)

    # Удаляем самую первую строку, где после shift(1) образовался NaN
    df = df.dropna().reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = load_telemetry_dataframe(Path("train_dataset.json"))
    print(f"Размер таблицы: {df.shape}")
    print(df.head())
