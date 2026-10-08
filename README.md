# VisionGuard AI — Hệ Thống Giám Sát Phòng Thi Trực Tuyến Thông Minh

Hệ thống giám sát tư thế thí sinh phòng thi thời gian thực thế hệ mới, tích hợp model **YOLO11-Pose** (từ repo [dyingangell/Cheating-detection-YOLO](https://github.com/dyingangell/Cheating-detection-YOLO)), **ByteTrack**, bộ đo độ lệch tư thế đầu (Normalized Head Offset & Torso Angle), bộ tự động hiệu chuẩn mốc cá nhân (Auto-Calibration EMA), bộ lọc phân biệt cúi viết bài vs quay cóp, và giao diện **Cyberpunk Tactical HUD (React + Vite + TypeScript)**. Tối ưu hoàn hảo cho cả máy tính để bàn và thiết bị di động (Responsive).

---

## 📑 Mục Lục
1. [Tính Năng Nổi Bật](#-tính-năng-nổi-bật)
2. [Cấu Trúc Thư Mục](#-cấu-trúc-thư-mục)
3. [Yêu Cầu Hệ Thống](#-yêu-cầu-hệ-thống)
4. [Hướng Dẫn Cài Đặt & Khởi Chạy](#-hướng-dẫn-cài-đặt--khởi-chạy)
   - [Cách 1: Khởi động nhanh (Khuyên dùng)](#cách-1-khởi-động-nhanh-khuyên-dùng)
   - [Cách 2: Khởi động thủ công từng phần](#cách-2-khởi-động-thủ-công-từng-phần)
   - [Cách kết nối từ xa trên Điện thoại (Cloudflare Tunnel)](#cách-kết-nối-từ-xa-trên-điện-thoại-cloudflare-tunnel)
   - [Cách kiểm thử bằng Video có sẵn](#cách-kiểm-thử-bằng-video-có-sẵn)
5. [Quy Chuẩn AI & Phát Hiện Hành Vi](#-quy-chuẩn-ai--phát-hiện-hành-vi)
6. [Hướng Dẫn Đẩy Code Lên GitHub](#-hướng-dẫn-đẩy-code-lên-github)
   - [Quy trình đẩy bản mới nhất](#1-quy-trình-đẩy-bản-mới-nhất-hằng-ngày)
   - [Xử lý khi bị lỗi xung đột (Conflict / Rejected)](#2-xử-lý-khi-gặp-xung-đột-conflict--rejected)

---

## 🌟 Tính Năng Nổi Bật

- **YOLO11-Pose & Multi-Person Tracking**: Nhận diện người, theo dõi liên tục qua **ByteTrack** và trích xuất đồng thời 17 điểm mốc xương khớp (COCO Pose Keypoints) chỉ trong 1 lần suy luận duy nhất (Single Forward Pass).
- **Thuật Toán Phát Hiện Gian Lận (dyingangell/Cheating-detection-YOLO)**:
  - Chuẩn hoá toạ độ mũi theo độ rộng vai (`rel_nose_x`, `rel_nose_y`).
  - Tự động lấy mốc tư thế cơ sở riêng cho từng thí sinh bằng giải thuật trung bình động luỹ thừa (`EMA Calibration`).
  - Phân tách độ lệch ngang (`lateral_dev` - quay nhìn bài thí sinh bên cạnh) và độ lệch dọc (`depth_dev` - cúi xuống viết bài), triệt tiêu báo động giả khi thí sinh cúi làm bài (`depth suppression`).
  - Bù trừ góc chụp nghiêng / camera gắn trần (`foreshortening compensation`).
- **Thang Điểm Nghi Vấn (Hazard Meter 0 - 100)**: Tích luỹ điểm nghi vấn theo thời gian (`score_s`), tự động giảm điểm khi trở về bình thường, phân loại trạng thái: `CALIBRATING`, `WITHIN_THRESHOLDS`, `OBSERVING`, `REVIEW`.
- **Tải Video Trực Tiếp (Video Test Suite)**: Cho phép tải file video (.mp4, .webm, .mov) lên thẳng Web HUD để giả lập bài thi mà không cần camera.
- **Cloudflare Tunnel Tích Hợp Sẵn**: 1 lệnh sinh link HTTPS công khai để giám thị theo dõi trực tiếp từ điện thoại hoặc máy tính bảng ở bất cứ đâu.
- **Giao diện Tactical HUD đỉnh cao**: Tối ưu hiển thị responsive, chế độ toàn màn hình, điều chỉnh FPS quét linh hoạt (15/30/60 FPS).

---

## 📂 Cấu Trúc Thư Mục

```text
exam-monitor/
├── frontend/                     # Giao diện React + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── camera/           # CameraView, CameraControls (Hỗ trợ Webcam + Upload Video)
│   │   │   ├── common/           # Header, ModelConfigModal (Cấu hình AI Server & Cloudflare Tunnel)
│   │   │   ├── candidate/        # Thẻ thông tin thí sinh, phân tích chi tiết
│   │   │   └── dashboard/        # Radar, Timeline sự kiện, Telemetry KPI
│   │   ├── hooks/                # useCamera, useMonitoringSocket (Tự động cấp vé & tái kết nối)
│   │   ├── pages/                # MonitorPage (Responsive Mobile & Desktop)
│   │   └── constants/            # Cấu hình API, WS URL
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                      # Máy chủ FastAPI + AI Pipeline
│   ├── app/
│   │   ├── main.py               # WebSocket & REST API
│   │   ├── sessions.py           # Quản lý luồng xử lý frame tuần tự
│   │   ├── protocol.py           # Pydantic Schemas dữ liệu chuẩn
│   │   └── inference/
│   │       ├── tracking_core.py  # YOLO11-Pose + ByteTrack
│   │       ├── pose_behavior.py  # Thuật toán Cheating-detection-YOLO (dyingangell)
│   │       └── pnp_head_pose.py  # Ước lượng tư thế 3D SolvePnP
│   ├── models/                   # Trọng số yolo11n-pose.pt, yolo11s-pose.pt, yolo11l-pose.pt, best.pt
│   ├── requirements.txt
│   └── Dockerfile
│
├── tools/
│   └── detect_cheating.py        # Công cụ chạy thử nghiệm trực tiếp camera/video với YOLO11-Pose HUD
├── scripts/
│   ├── start-ai-server.sh        # Khởi động Backend + Cloudflare Tunnel tự động
│   ├── start_backend.sh          # Khởi động Backend độc lập
│   ├── start_tunnel.sh           # Mở Cloudflare Tunnel
│   └── run_tests.sh              # Chạy bộ kiểm thử tự động
├── package.json                  # Scripts quản lý toàn bộ workspace
├── README.md                     # Tài liệu hướng dẫn sử dụng
└── .gitignore                    # Loại trừ file rác, weights nặng & token bí mật
```

---

## 💻 Yêu Cầu Hệ Thống

- **Hệ điều hành**: macOS, Ubuntu/Linux, hoặc Windows (WSL2).
- **Node.js**: Phiên bản 18.x trở lên (`node -v`).
- **Python**: Phiên bản 3.10 hoặc 3.11 (`python3 -v`).
- **Git**: Đã cài đặt và kết nối SSH hoặc HTTPS với GitHub.

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### Cài đặt ban đầu (Lần đầu tiên)

1. **Cài đặt thư viện Frontend:**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

2. **Cài đặt môi trường Backend:**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate       # Trên Windows: .venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   cd ..
   ```

3. **Tải file trọng số AI Model (YOLO11-Pose):**
   ```bash
   python3 backend/models/download_models.py
   ```
   *(Trọng số `yolo11n-pose.pt`, `yolo11s-pose.pt`, `yolo11l-pose.pt` được lưu tự động trong `backend/models/`. Hệ thống cũng hỗ trợ file custom `best.pt` nếu có).*

---

### Cách 1: Khởi động nhanh (Khuyên dùng)

Tại thư mục gốc của dự án (`exam-monitor`):

1. **Bật AI Backend & Đường hầm Cloudflare Tunnel:**
   ```bash
   npm run ai-server
   ```
   *Lệnh này sẽ tự động chạy FastAPI trên cổng `8000` và hiển thị link Cloudflare công khai (dạng `https://xxxx.trycloudflare.com`).*

2. **Mở một Terminal mới, khởi động Frontend:**
   ```bash
   npm run dev
   ```
   *Truy cập trình duyệt tại: **`http://localhost:5173`***.

---

### Cách 2: Khởi động thủ công từng phần

#### 1. Khởi động AI Backend:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Kiểm tra tài liệu Swagger API: `http://localhost:8000/docs`
- Kiểm tra trạng thái: `http://localhost:8000/api/v1/health`

#### 2. Khởi động Frontend:
```bash
cd frontend
npm run dev
```

---

### 📱 Cách kết nối từ xa trên Điện thoại (Cloudflare Tunnel)

1. Khi chạy `npm run ai-server`, terminal sẽ xuất hiện dòng:
   ```text
   Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):
   https://random-subdomain.trycloudflare.com
   ```
2. Copy đường link `https://random-subdomain.trycloudflare.com`.
3. Mở giao diện Web trên Điện thoại hoặc Laptop khác (qua link Vercel hoặc mạng LAN).
4. Nhấn vào biểu tượng **⚙️ Cài Đặt** ở góc phải thanh Header.
5. Dán link vừa copy vào ô **"Địa chỉ AI Backend"** $\rightarrow$ Nhấn **"Lưu Cấu Hình"**.
6. Nhấn **"Bật Camera"** hoặc **"Tải Video Lên"** để bắt đầu giám sát!

---

### 🎥 Cách kiểm thử bằng Video có sẵn

Nếu không có webcam hoặc muốn thử nghiệm các tình huống quay cóp mẫu:
1. Nhấn nút **"📁 Tải Video Lên"** ngay cạnh nút Bật Camera.
2. Chọn video định dạng `.mp4`, `.mov` hoặc `.webm`.
3. Trình phát sẽ tự động trích xuất từng khung hình và truyền qua AI WebSocket để phân tích thời gian thực giống hệt như camera trực tiếp.

---

## 🎯 Quy Chuẩn AI & Phát Hiện Hành Vi

- **Hiệu chuẩn góc nhìn (Calibration)**: Tự động ghi nhận 20 khung hình đầu tiên để tính góc Yaw cơ sở ($Yaw_0$) và độ cao mũi ($NoseY_0$).
- **Quay đầu bất thường (Turning Head)**: Chênh lệch $|\Delta Yaw| > 35^\circ$.
- **Cúi người / Nhìn tài liệu (Bending Down)**: Hạ mũi $NoseY - NoseY_0 > 0.15 \times \text{Chiều cao khung hình}$.
- **Cảnh báo vi phạm (Trigger REVIEW)**: Khi duy trì trạng thái bất thường liên tục $\ge 1.5$ giây.

---

## 🐙 Hướng Dẫn Đẩy Code Lên GitHub

### 1. Quy trình đẩy bản mới nhất hằng ngày

Khi bạn đã sửa đổi code hoặc thêm tính năng mới, mở Terminal tại thư mục dự án và chạy các lệnh sau:

```bash
# Bước 1: Kiểm tra trạng thái các file đã thay đổi
git status

# Bước 2: Thêm tất cả thay đổi vào vùng chuẩn bị commit
git add .

# Bước 3: Tạo commit với thông điệp rõ ràng
git commit -m "feat: cập nhật mô tả tính năng mới"

# Bước 4: Đẩy lên nhánh main trên GitHub
git push origin main
```

---

### 2. Xử lý khi gặp xung đột (Conflict / Rejected)

Nếu trên GitHub có người khác sửa hoặc bạn vừa cập nhật trên máy tính khác dẫn đến việc bị từ chối push:

```bash
# 1. Kéo code mới nhất về và ghép vào nhánh hiện tại
git pull --rebase origin main

# 2. Nếu có xung đột, mở file xử lý conflict rồi đánh dấu đã sửa:
git add .
git rebase --continue

# 3. Đẩy lại lên GitHub
git push origin main
```

---

### 3. Các lệnh Git tiện ích hay dùng

- **Xem lịch sử commit ngắn gọn:**
  ```bash
  git log --oneline -n 5
  ```
- **Tạm cất các thay đổi chưa xong để kéo code mới:**
  ```bash
  git stash
  git pull origin main
  git stash pop
  ```
- **Hủy bỏ các sửa đổi chưa commit của một file:**
  ```bash
  git checkout -- <tên-file>
  ```

---

## 🛡️ Bản Quyền & Giấy Phép
Dự án được phát triển phục vụ mục đích nghiên cứu & ứng dụng giám sát phòng thi thông minh.  
Mọi thắc mắc và đóng góp xin vui lòng tạo Issue hoặc Pull Request trên repository.
