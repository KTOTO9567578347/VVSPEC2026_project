FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# 8000 — REST/WebSocket для фронта, 50051 — gRPC для ноды grpc_bridge
EXPOSE 8000 50051

CMD ["python", "-m", "app"]
