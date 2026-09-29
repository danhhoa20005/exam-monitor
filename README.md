# VisionGuard AI — Realtime Exam Posture Surveillance (Pro Max Edition)

Hệ thống giám sát tư thế phòng thi trực tuyến thời gian thực chuẩn công nghệ cao sử dụng **YOLOv8**, **ByteTrack** và **MediaPipe Tasks Pose Landmarker**.

---

## 🏗️ Cấu Trúc Toàn Bộ Dự Án

```text
Ai/
├── frontend/                           # Giao diện React + TypeScript + Vite (Pro Max HUD)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx              # HUD Top bar, đồng hồ phiên, Threat meter, Audio
│   │   │   ├── CameraView.tsx          # Khung video HUD reticles, Radar beam, Scanlines toggle
│   │   │   ├── TrackOverlay.tsx        # Overlay Canvas đa lớp, thước đo góc Yaw, thanh hazard
│   │   │   ├── CandidateCards.tsx      # Lưới thẻ giám sát tư thế realtime từng thí sinh
│   │   │   ├── CandidateDetailModal.tsx# Cửa sổ phân tích sâu hồ sơ tư thế & lịch sử sự kiện
│   │   │   ├── EventPanel.tsx          # Luồng sự kiện nghi vấn & thao tác duyệt của giám thị
│   │   │   ├── MetricsPanel.tsx        # Bảng KPI telemetry hiệu năng AI
│   │   │   ├── CalibrationGuide.tsx    # Hướng dẫn hiệu chuẩn 20 mẫu tham chiếu
│   │   │   └── LoginModal.tsx          # Hộp thoại danh tính giám thị
│   │   ├── hooks/
│   │   │   ├── useCamera.ts            # Điều khiển webcam, lật gương, quét frame JPEG 0.75
│   │   │   ├── useMonitoringSession.ts # Bộ máy mô phỏng đa thí sinh + WebSocket client
│   │   │   └── useAudioAlert.ts        # Bộ tổng hợp âm thanh Web Audio cảnh báo
│   │   ├── types/
│   │   │   └── protocol.ts             # TypeScript protocol types
│   │   ├── App.tsx                     # Bố cục trung tâm chỉ huy
│   │   ├── App.css                     # Phong cách Cyberpunk HUD
│   │   ├── index.css                   # Design tokens neon & animations
│   │   └── main.tsx
│   ├── dist/                           # Production bundle tĩnh đã build sẵn
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── vercel.json                     # Cấu hình deploy Vercel
│
├── backend/                            # Máy chủ AI FastAPI + YOLOv8 + ByteTrack + MediaPipe
│   ├── app/
│   │   ├── main.py                     # FastAPI WebSocket & REST Endpoints
│   │   ├── auth.py                     # Xác thực & vé WS ticket
│   │   ├── sessions.py                 # Quản lý phiên & luồng inference tuần tự
│   │   ├── protocol.py                 # Pydantic schemas
│   │   ├── config.py                   # Cấu hình & ngưỡng thuật toán (35° yaw, 15% hạ mũi)
│   │   └── inference/
│   │       ├── tracking_core.py        # Pipeline YOLOv8 + ByteTrack
│   │       ├── pose_behavior.py        # MediaPipe Tasks Pose + Lấy mốc 20 mẫu + Rule engine
│   │       ├── events.py               # Gom nhóm sự kiện & bộ xuất CSV/JSON
│   │       └── pnp_head_pose.py        # SolvePnP 3D Euler Angles (EPnP + Iterative)
│   ├── models/
│   │   ├── download_models.py          # Tự động tải Pose model & kiểm tra SHA-256
│   │   └── README.md                   # Hướng dẫn copy best.pt
│   ├── config/
│   │   └── bytetrack.yaml              # Cấu hình ByteTrack
│   ├── tests/                          # Bộ unit test & integration test
│   │   ├── test_protocol.py
│   │   ├── test_pnp.py
│   │   ├── test_pose_behavior.py
│   │   ├── test_events.py
│   │   └── test_api.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── scripts/
│   ├── start_backend.sh                # Script khởi động FastAPI Backend
│   ├── start_tunnel.sh                 # Script mở Cloudflare Quick Tunnel cho demo
│   └── run_tests.sh                    # Script chạy toàn bộ test
├── README.md
└── .gitignore
```

---

## 📥 1. Hướng Dẫn Ghép AI Model Đã Train Vào

### Bước 1: Sao chép file `best.pt`
Chỉ cần copy file trọng số mô hình đã huấn luyện của bạn vào đường dẫn:
```text
backend/models/best.pt
```

### Bước 2: Kiểm tra Checksum SHA-256
Chạy lệnh sau để hệ thống tự động kiểm tra mã băm và tải `pose_landmarker_lite.task`:
```bash
python3 backend/models/download_models.py
```
*Mã SHA-256 tiêu chuẩn theo đặc tả: `c1ea0a60e07a33c4bd01263e261e644cd74cf2520d164acf9512f5828512bbe1`*

---

## 🚀 2. Khởi Chạy Ứng Dụng

### Khởi động Frontend
```bash
cd frontend
npm run dev
```
Truy cập: **`http://localhost:5173`**

### Khởi động Backend (Sau khi cài thư viện Python)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```
Hoặc dùng script:
```bash
./scripts/start_backend.sh
```

### Mở Tunnel Demo Ra Mạng Ngoài (Cloudflare Tunnel)
```bash
./scripts/start_tunnel.sh
```

---

## 🎯 3. Quy Chuẩn Đánh Giá Tư Thế (As Per Specification)

- **Hiệu chuẩn (Calibration)**: Thu thập đủ **20 mẫu Pose hợp lệ liên tiếp** để tính trung vị Yaw ($Yaw_0$) và tọa độ Y của mũi ($NoseY_0$).
- **Quay đầu (Turning)**: $|\Delta Yaw| > 35^\circ$ với $\Delta Yaw = ((Yaw - Yaw_0 + 180) \bmod 360) - 180$.
- **Hạ người (Bending)**: $NoseY - NoseY_0 > 0.15 \times H$ (chiều cao toàn khung hình).
- **Kích hoạt Nghi vấn (REVIEW)**: Khi một trong hai hành vi vượt ngưỡng liên tục $\ge 1.5$ giây.
- **Gián đoạn (Gap)**: Khoảng trống $> 2.5$ giây tự động reset bộ đếm thời gian.
- **Nhãn tự động**: Luôn hiển thị **"Nghi vấn — cần xem lại"** kèm nguyên nhân, quyết định xử lý vi phạm thuộc về Giám thị.
