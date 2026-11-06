from fastapi import APIRouter, Request

from app import __version__
from app.schemas import Health

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=Health, summary="Проверка живости")
def health(request: Request):
    db_ok = request.app.state.db.ping()
    return Health(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        grpc_port=request.app.state.grpc_port,
        version=__version__,
    )
