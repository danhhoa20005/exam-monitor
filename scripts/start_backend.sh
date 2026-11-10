#!/usr/bin/env bash
# Script khởi động nhanh AI Model Backend (VisionGuard AI)

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR/backend"

# Always use the project virtualenv: the system Python usually lacks ultralytics/torch.
PYTHON_BIN="$BASE_DIR/backend/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "[*] Creating backend virtualenv..."
    "$(command -v python3)" -m venv "$BASE_DIR/backend/.venv"
    PYTHON_BIN="$BASE_DIR/backend/.venv/bin/python3"
    echo "[*] Installing backend dependencies..."
    "$PYTHON_BIN" -m pip install -r requirements.txt
fi
UVICORN_BIN="$BASE_DIR/backend/.venv/bin/uvicorn"
if [ ! -x "$UVICORN_BIN" ]; then
    UVICORN_BIN="$BASE_DIR/backend/.venv/bin/uvicorn"
fi

echo "======================================================="
echo "   Khởi động AI Backend (YOLO11-Pose + turn_cls + YOLO11m)"
echo "======================================================="

# Tải yolo11l-pose.pt và yolo11m.pt nếu chưa có (turn_cls.pt đã có sẵn trong repo)
"$PYTHON_BIN" models/download_models.py

echo "[*] Đang khởi động FastAPI Uvicorn Server tại http://0.0.0.0:8000..."
echo "[*] Mở giao diện: http://localhost:8000 (cần build frontend trước: npm run build)"
echo "======================================================="

"$UVICORN_BIN" app.main:app --host 0.0.0.0 --port 8000 --reload
