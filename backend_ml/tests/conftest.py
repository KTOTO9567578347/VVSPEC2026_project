import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.services.ingest import ingest_batch, now_ms


def make_point(ts, status="OK", x=0.0, y=0.0, yaw=0.0, cmd=(0.0, 0.0), odom=(0.0, 0.0), msg=None):
    ok = status == "OK"
    return {
        "timestamp_ms": ts,
        "status": status,
        "status_message": msg,
        "x": x if ok else None,
        "y": y if ok else None,
        "yaw": yaw if ok else None,
        "cmd_linear_x": cmd[0],
        "cmd_angular_z": cmd[1],
        "odom_linear_x": odom[0],
        "odom_angular_z": odom[1],
    }


@pytest.fixture
def settings():
    return Settings(database_url="sqlite://", grpc_port=0, grpc_host="127.0.0.1")


@pytest.fixture
def db(settings):
    database = Database(settings.database_url)
    database.create_all()
    return database


@pytest.fixture
def client(settings, db):
    app = create_app(settings=settings, db=db, start_grpc=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded(db):
    """Робот проехал 10 точек по прямой x = 0..0.9 со скоростью 0.1 м/шаг (шаг 100 мс → 1 м/с),
    потом 3 точки без TF."""
    t0 = now_ms() - 60_000
    pts = [make_point(t0 + i * 100, x=i * 0.1, cmd=(1.0, 0.0), odom=(0.9, 0.0)) for i in range(10)]
    pts += [make_point(t0 + 1000 + i * 100, status="NOTF", cmd=(1.0, 0.0), odom=(0.9, 0.0), msg="no tf")
            for i in range(3)]
    with db.session() as s:
        ingest_batch(s, "r1", pts)
    return {"robot_id": "r1", "t0": t0, "t_end": t0 + 1200}
