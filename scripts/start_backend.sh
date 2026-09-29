#!/usr/bin/env bash
# Script khởi động nhanh AI Model Backend (VisionGuard AI)

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR/backend"

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
python3 models/download_models.py

echo "[*] Đang khởi động FastAPI Uvicorn Server tại http://0.0.0.0:8000..."
echo "[*] WebSocket endpoint: ws://0.0.0.0:8000/ws/sessions/session-01"
echo "======================================================="

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
