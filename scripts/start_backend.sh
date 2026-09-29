#!/usr/bin/env bash
# Script khởi động nhanh AI Model Backend (VisionGuard AI)

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR/backend"

# Always use the project virtualenv when it exists. Using the system Python
# silently caused YOLO/MediaPipe to be unavailable even though the model file
# was present.
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
echo "   Khởi Động VisionGuard AI Backend (YOLOv8 + MediaPipe)   "
echo "======================================================="

# Kiểm tra weights model
if [ ! -f "models/best.pt" ]; then
    echo "[!] Không tìm thấy models/best.pt. Đang copy từ thư mục model/..."
    if [ -f "../model/extracted/weights/best.pt" ]; then
        cp ../model/extracted/weights/best.pt models/best.pt
        echo "[OK] Đã copy weights/best.pt vào backend/models/best.pt"
    fi
fi

# Tải model MediaPipe Pose nếu chưa có
"$PYTHON_BIN" models/download_models.py

echo "[*] Đang khởi động FastAPI Uvicorn Server tại http://0.0.0.0:8000..."
echo "[*] WebSocket endpoint: ws://0.0.0.0:8000/ws/sessions/session-01"
echo "======================================================="

"$UVICORN_BIN" app.main:app --host 0.0.0.0 --port 8000 --reload
