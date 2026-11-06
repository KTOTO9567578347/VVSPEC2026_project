from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бэкенда. Любое поле можно переопределить переменной окружения
    с префиксом BACKEND_ (например, BACKEND_DATABASE_URL) или через файл .env."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BACKEND_", extra="ignore")

    # По умолчанию SQLite, чтобы можно было запустить без Docker.
    # Для Postgres: postgresql+psycopg://user:pass@host:5432/dbname
    database_url: str = "sqlite:///./telemetry.db"

    http_host: str = "0.0.0.0"
    http_port: int = 8000

    # Порт должен совпадать с grpc_settings.server_address в simulator_container/config.json
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051
    grpc_workers: int = 8

    # Список origin'ов для CORS (JSON-список в env: '["http://localhost:5173"]')
    cors_origins: list[str] = ["*"]

    # Нода шлёт батчи раз в 5 секунд, поэтому робот считается онлайн,
    # если последний батч пришёл не позже чем timeout секунд назад.
    robot_online_timeout_s: float = 15.0

    # Окно по умолчанию для метрик/телеметрии, если from/to не заданы.
    default_window_s: int = 600

    # Порог скорости, ниже которого робот считается стоящим.
    idle_speed_eps: float = 0.01

    # Разрыв между точками, после которого считаем, что данных не было (мс).
    max_gap_ms: int = 2000

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
