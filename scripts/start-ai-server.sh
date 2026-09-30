#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

echo "================================================================"
echo "🚀 Khởi động VisionGuard AI Server & Cloudflare Tunnel..."
echo "================================================================"

# Dừng các tiến trình cũ trên port 8000 nếu có
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Khởi chạy AI Backend ở chế độ ngầm (Background)
echo "1️⃣ Đang khởi động AI Backend (YOLOv8 & MediaPipe) trên port 8000..."
cd backend

PYTHON_BIN="$BASE_DIR/backend/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3)"
fi
UVICORN_BIN="$BASE_DIR/backend/.venv/bin/uvicorn"
if [ ! -x "$UVICORN_BIN" ]; then
    UVICORN_BIN="uvicorn"
fi

"$UVICORN_BIN" app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
cd "$BASE_DIR"

sleep 2
echo "✅ AI Backend đã khởi động thành công (PID: $BACKEND_PID)."
echo ""
echo "2️⃣ Đang kết nối Cloudflare Tunnel ra Internet..."
echo "----------------------------------------------------------------"
echo "📌 HƯỚNG DẪN DÀNH CHO BẠN:"
echo "1. Đợi đường link dạng: https://xxxx.trycloudflare.com hiển thị bên dưới."
echo "2. Copy đường link đó."
echo "3. Mở web giám sát (Vercel/Điện thoại), bấm icon Cài Đặt (⚙️) ở góc trên."
echo "4. Dán link vừa copy vào ô 'Máy Chủ AI Backend' rồi bấm 'Lưu Cấu Hình'."
echo "5. Bấm 'Bật Camera' để bắt đầu giám sát trực tiếp!"
echo "----------------------------------------------------------------"
echo "👉 Nhấn Ctrl + C khi muốn tắt server."
echo ""

# Bắt sự kiện thoát (Ctrl+C) để kill luôn backend
trap "echo 'Đang dừng server...'; kill $BACKEND_PID 2>/dev/null || true; exit 0" SIGINT SIGTERM EXIT

# Khởi chạy Cloudflare Tunnel
npx --yes cloudflared tunnel --protocol http2 --url http://127.0.0.1:8000
