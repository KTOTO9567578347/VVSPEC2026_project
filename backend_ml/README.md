# backend_ml — бэкенд метрик робота

Принимает телеметрию от ROS2-ноды `grpc_bridge` по gRPC, складывает её в БД,
считает метрики и отдаёт всё фронтенду через REST и WebSocket.

```
ROS2 / симулятор ──gRPC :50051──▶ backend ──▶ PostgreSQL / SQLite
 (grpc_bridge)   TelemetryBatch     │
                                    └──HTTP :8000──▶ frontend (REST + WebSocket)
```

Контракт gRPC — общий файл
`simulator_container/packages/grpc_bridge/proto/telemetry.proto`.
Стабы для Python лежат в `app/grpc_gen/`; после изменения proto их надо перегенерировать:

```bash
bash scripts/gen_proto.sh
```

## Запуск

### Через Docker (бэкенд + Postgres)

```bash
cd backend_ml
docker compose up -d --build
```

API: http://localhost:8000, Swagger: http://localhost:8000/docs, gRPC: `localhost:50051`.
Нода из `simulator_container` (там `network_mode: host`) по умолчанию шлёт на `localhost:50051`,
так что ничего менять не надо.

### Локально (SQLite, без Docker)

```bash
cd backend_ml
python -m venv .venv
# Windows: .venv\Scripts\activate   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app
```

База создастся в `telemetry.db`. Настройки — переменные окружения с префиксом `BACKEND_`
или файл `.env` (пример в `.env.example`).

### Эмулятор робота (без ROS)

Чтобы разрабатывать фронт без симулятора:

```bash
python scripts/fake_robot.py                              # один робот, как нода: 20 Гц, батч раз в 5 с
python scripts/fake_robot.py --robots 3 --batch-interval 1  # три робота, батчи каждую секунду
```

### Тесты

```bash
pytest
```

## API

Все времена — unix-время в **миллисекундах**. Если у запроса нет `from_ms`/`to_ms`,
берутся последние `window_s` секунд (по умолчанию 600) до самой свежей точки робота.

| Метод | Путь | Что возвращает |
|---|---|---|
| GET | `/api/health` | состояние БД и gRPC |
| GET | `/api/robots` | список роботов: `online`, счётчики, последняя точка |
| GET | `/api/robots/{id}` | один робот |
| DELETE | `/api/robots/{id}` | удалить робота и всю его телеметрию |
| GET | `/api/robots/{id}/telemetry` | сырые точки за диапазон, `max_points` — прореживание |
| GET | `/api/robots/{id}/telemetry/latest` | последняя точка |
| GET | `/api/robots/{id}/trajectory` | `[{t, x, y, yaw}]` — только точки с позой, для карты |
| GET | `/api/robots/{id}/metrics` | сводные метрики за диапазон |
| GET | `/api/robots/{id}/metrics/timeseries` | метрики по интервалам `bucket_s` — для графиков |
| GET | `/api/robots/{id}/events` | участки без TF (`NOTF`), ошибки (`ERROR`), разрывы связи (`GAP`) |
| WS | `/ws/live?robot_id=...` | новые точки на каждый батч; без `robot_id` — от всех роботов |

Общие query-параметры для диапазона: `from_ms`, `to_ms`, `window_s`.

### Точка телеметрии

```json
{
  "timestamp_ms": 1793534332670,
  "status": "OK",
  "status_message": null,
  "pose": {"x": 0.69, "y": 0.51, "yaw": -0.49},
  "cmd_vel": {"linear_x": 0.25, "angular_z": 0.1},
  "odom_vel": {"linear_x": 0.24, "angular_z": 0.09}
}
```

`pose` равен `null`, когда TF не нашёлся (`status: "NOTF"`).

### Метрики (`/metrics`)

| Поле | Смысл |
|---|---|
| `samples`, `duration_s` | сколько точек и какой отрезок времени |
| `status_counts`, `tf_availability` | счётчики статусов и доля точек с `OK` |
| `distance_m` | пройденный путь по позе (скачки после разрывов не считаются) |
| `displacement_m`, `path_efficiency` | расстояние от старта до финиша и его отношение к пути |
| `total_rotation_rad` | суммарный поворот |
| `avg_speed_mps`, `max_speed_mps` | средняя/максимальная скорость по одометрии |
| `path_speed_mps` | путь / время |
| `avg_angular_speed_rps` | средняя угловая скорость |
| `idle_ratio`, `moving_ratio` | доля времени с нулевой командой / с реальным движением |
| `linear_tracking`, `angular_tracking` | ошибка «команда − одометрия»: `rmse`, `mae`, `max_abs` |
| `gaps`, `gap_time_s` | сколько раз пропадали данные (дольше `max_gap_ms`) и на сколько |

### Пример для фронта

```js
const robots = await fetch("http://localhost:8000/api/robots").then(r => r.json());

const ws = new WebSocket("ws://localhost:8000/ws/live?robot_id=robot_v1_simulation");
ws.onmessage = (e) => {
  const { robot_id, points } = JSON.parse(e.data);
  // дорисовать points на графике/карте
};
```

## Структура

```
app/
  __main__.py      запуск: python -m app (HTTP + gRPC в одном процессе)
  main.py          сборка FastAPI-приложения, старт/стоп gRPC-сервера
  config.py        настройки (env BACKEND_*)
  db.py, models.py SQLAlchemy: robots, telemetry_points, telemetry_batches
  grpc_server.py   реализация TelemetryService.SendTelemetryBatch
  grpc_gen/        сгенерированные стабы из telemetry.proto
  services/        запись батчей, запросы к БД, расчёт метрик, live-рассылка
  api/             REST- и WebSocket-эндпоинты
scripts/
  gen_proto.sh     перегенерация стабов
  fake_robot.py    эмулятор робота
tests/
```

Таблицы создаются автоматически при старте (`create_all`), миграций пока нет —
если поменяется схема, проще пересоздать базу (`docker compose down -v`).
