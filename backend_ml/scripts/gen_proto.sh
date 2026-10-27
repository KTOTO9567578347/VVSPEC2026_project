#!/usr/bin/env bash
# Перегенерирует Python-стабы из общего telemetry.proto.
# Запускать из папки backend_ml:  bash scripts/gen_proto.sh
# Нужен grpcio-tools (есть в requirements-dev.txt).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROTO_DIR="${PROTO_DIR:-$ROOT/../simulator_container/packages/grpc_bridge/proto}"
OUT_DIR="$ROOT/app/grpc_gen"

python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$OUT_DIR" \
  --pyi_out="$OUT_DIR" \
  --grpc_python_out="$OUT_DIR" \
  "$PROTO_DIR/telemetry.proto"

# protoc генерирует абсолютный импорт, внутри пакета нужен относительный
sed -i.bak 's/^import telemetry_pb2 as telemetry__pb2/from . import telemetry_pb2 as telemetry__pb2/' \
  "$OUT_DIR/telemetry_pb2_grpc.py"
rm -f "$OUT_DIR/telemetry_pb2_grpc.py.bak"

echo "Стабы обновлены в $OUT_DIR"
