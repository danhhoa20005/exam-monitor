#!/bin/bash
echo "================================================================"
echo "🚀 Khởi động VisionGuard AI Server & Kết Nối Internet..."
echo "================================================================"

# Dừng các tiến trình cũ nếu có
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Khởi chạy AI Backend ở chế độ ngầm (Background)
echo "1️⃣ Đang khởi động AI Backend (YOLOv8 & MediaPipe) trên port 8000..."
cd backend
/Users/MAC/miniconda3/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
cd ..

sleep 3
echo "[OK] AI Backend đã chạy ngầm (PID: $BACKEND_PID)."

# Khởi chạy LocalTunnel để mở port ra Internet
echo "2️⃣ Đang mở cổng kết nối Internet qua LocalTunnel..."
echo "----------------------------------------------------------------"
echo "📌 HƯỚNG DẪN DÀNH CHO BẠN:"
echo "1. Đợi dòng chữ 'your url is: https://...' xuất hiện bên dưới."
echo "2. Giữ Cmd (⌘) và click vào link đó để mở trên trình duyệt, sau đó bấm 'Click to Continue' để xác thực."
echo "3. Copy link đó, thêm 'wss://' thay cho 'https://' và nối thêm '/ws/sessions/session-01'."
echo "   (Ví dụ: wss://xxx.loca.lt/ws/sessions/session-01)"
echo "4. Dán link vừa tạo vào mục Cài Đặt Model trên giao diện Vercel để AI bắt đầu hoạt động!"
echo "----------------------------------------------------------------"

# Chạy LocalTunnel
npx localtunnel --port 8000

# Bắt sự kiện thoát (Ctrl+C) để kill luôn backend
trap "kill $BACKEND_PID" EXIT
