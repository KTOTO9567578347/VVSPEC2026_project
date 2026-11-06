"""Запуск: python -m app  (HTTP API + gRPC-сервер в одном процессе)."""

import logging

import uvicorn

from app.config import get_settings
from app.main import create_app


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(create_app(settings), host=settings.http_host, port=settings.http_port, log_level="info")


if __name__ == "__main__":
    main()
