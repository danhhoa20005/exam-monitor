#!/bin/bash
echo "================================================================"
echo "🚀 Khởi động VisionGuard AI Server & Kết Nối Internet..."
echo "================================================================"

# Dừng các tiến trình cũ nếu có
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Khởi chạy AI Backend ở chế độ ngầm (Background)
echo "1️⃣ Đang khởi động AI Backend (YOLOv8 & MediaPipe) trên port 8000..."
cd backend
if command -v uvicorn &> /dev/null; then
    uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
elif [ -f "/Users/MAC/miniconda3/bin/uvicorn" ]; then
    /Users/MAC/miniconda3/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
else
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
fi
BACKEND_PID=$!
cd ..

sleep 3
echo "[OK] AI Backend đã chạy ngầm (PID: $BACKEND_PID)."

# Khởi chạy LocalTunnel để mở port ra Internet
echo "2️⃣ Đang mở cổng kết nối Internet qua LocalTunnel..."
echo "----------------------------------------------------------------"
echo "📌 HƯỚNG DẪN DÀNH CHO BẠN:"
echo "1. Đợi dòng chữ 'your url is: https://...' xuất hiện bên dưới."
echo "2. Copy đường link 'https://...loca.lt' đó."
echo "3. Mở web giám sát đã deploy (Vercel/Firebase), bấm icon Cài Đặt (⚙️) ở góc trên."
echo "4. Dán link vừa copy vào ô 'Máy Chủ AI Backend' rồi bấm 'Lưu Cấu Hình' để AI kết nối ngay lập tức!"
echo "----------------------------------------------------------------"

# Chạy LocalTunnel
npx localtunnel --port 8000

# Bắt sự kiện thoát (Ctrl+C) để kill luôn backend
trap "kill $BACKEND_PID" EXIT
