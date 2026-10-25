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
│   │       ├── tracking_core.py  # YOLO11-Pose + ByteTrack + phát hiện điện thoại, reset khi đổi nguồn video
│   │       ├── pose_behavior.py  # Luật hành vi: quay đầu (mốc riêng từng người), cúi, điện thoại
│   │       ├── turn_classifier.py# Model turn_cls của nhóm: phân loại quay đầu trên ảnh cắt từng người
│   │       └── pnp_head_pose.py  # Hàm góc (chuẩn hoá ±180°)
│   ├── models/                   # turn_cls.pt (nhóm train, có sẵn); yolo11l-pose.pt, yolo11m.pt tự tải
│   ├── requirements.txt
│   └── Dockerfile
│
├── training/                     # Chuẩn bị dữ liệu, train, đánh giá (xem training/README.md)
│   └── results/                  # Nhật ký 10 vòng cải thiện, bảng đánh giá, biểu đồ train
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

3. **Trọng số AI Model:** không cần tải tay. Lần chạy backend đầu tiên (cần Internet) sẽ tự tải
   `yolo11l-pose.pt` (tìm thí sinh + 17 điểm khớp) và `yolo11m.pt` (phát hiện điện thoại) vào `backend/models/`.
   Model do nhóm train `turn_cls.pt` đã có sẵn trong repo. Tắt model nào bằng biến môi trường trước khi chạy,
   vd `TURN_CLS_MODEL=none.pt` hoặc `PHONE_MODEL=none.pt`.

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

Mỗi khung hình (960 px, ~64 ms trên RTX 4060) đi qua 3 model: **YOLO11-Pose** tìm thí sinh + 17 điểm khớp,
**turn_cls** (nhóm train) đoán quay đầu trên ảnh cắt từng người, **YOLO11m** tìm điện thoại. Luật hành vi gộp lại:

- **Lấy mốc (Calibration)**: 20 mẫu đầu của mỗi thí sinh, lấy **trung vị** vị trí mũi, góc đầu và P(turn) — một cú liếc
  ngắn trong lúc lấy mốc không làm lệch mốc. Đổi camera / tải video khác → xoá toàn bộ track và lấy mốc lại.
- **Quay đầu (TURNING)**, kéo dài $\ge 1.5$ giây, khi có một trong:
  - góc quay đầu từ mũi so với hai tai lệch mốc $> 35^\circ$; tai xa bị che + mũi lệch khỏi giữa hai mắt được coi là quay ~60°
    (chỉ khi người đủ lớn trong khung hình, vai $\ge 9\%$ chiều rộng ảnh);
  - mũi lệch ngang so với vai vượt bán kính cho phép (bù góc camera);
  - P(turn) của turn_cls (làm mượt) $\ge 0.8$ **và** cao hơn mốc riêng của thí sinh $\ge 0.5$.
- **Dùng điện thoại (PHONE)**, kéo dài $\ge 1$ giây: khung "cell phone" (độ tin cậy $\ge 0.3$) cách cổ tay $\le 0.5$ lần độ rộng vai,
  nhỏ và dài như điện thoại thật (diện tích $\le 0.05$ vai², tỉ lệ dài/rộng $\ge 1.3$) — loại tay cầm bút bị nhận nhầm.
- **Cúi người (BENDING)**: chỉ là nhãn đi kèm, không tự gây cảnh báo (cúi viết bài là bình thường).

Kết quả trên tập test DS-03 (sinh viên 5–8, không dùng để chỉnh): nhìn bài bạn 4/4, điện thoại 5/8,
**báo nhầm người bình thường 0/16**. Chi tiết: [`training/README.md`](training/README.md).

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
