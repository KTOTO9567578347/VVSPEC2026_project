from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_sqlite_memory(url: str) -> bool:
    return url in ("sqlite://", "sqlite:///:memory:")


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if _is_sqlite(url):
        # gRPC-сервер пишет из своих потоков, FastAPI читает из своих
        kwargs["connect_args"] = {"check_same_thread": False}
        if _is_sqlite_memory(url):
            # одна общая in-memory база на все соединения (нужно для тестов)
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True

    engine = create_engine(url, **kwargs)

    if _is_sqlite(url):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            if not _is_sqlite_memory(url):
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


class Database:
    """Обёртка над engine + фабрикой сессий."""

    def __init__(self, url: str):
        self.url = url
        self.engine = make_engine(url)
        self.sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        from app import models  # noqa: F401  регистрирует таблицы в metadata

        Base.metadata.create_all(self.engine)

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.sessionmaker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
