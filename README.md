# VisionGuard AI — Hệ Thống Giám Sát Phòng Thi Trực Tuyến Thông Minh

Hệ thống hỗ trợ giám thị phát hiện gian lận trong phòng thi từ camera thường, theo thời gian thực: **YOLO11-Pose** + **ByteTrack** theo dõi từng thí sinh, **turn_cls** (mô hình phân loại quay đầu do nhóm huấn luyện), **YOLO11m** phát hiện điện thoại, và bộ luật so mỗi thí sinh với **mốc tư thế riêng** của chính họ. Giao diện **React + Vite + TypeScript** cho giám thị: cảnh báo, clip bằng chứng, biên bản ca thi. Đánh giá trên bộ video DS-03: nhìn bài bạn 4/4, điện thoại 6/8, **0/16 báo nhầm** (tập test).

---

## 📑 Mục Lục
1. [Tính Năng Nổi Bật](#-tính-năng-nổi-bật)
2. [Cấu Trúc Thư Mục](#-cấu-trúc-thư-mục)
3. [Yêu Cầu Hệ Thống](#-yêu-cầu-hệ-thống)
4. [Hướng Dẫn Cài Đặt & Khởi Chạy](#-hướng-dẫn-cài-đặt--khởi-chạy)
   - [Cách 1: Một máy chủ (khuyên dùng, cũng là cách demo)](#cách-1-một-máy-chủ-khuyên-dùng-cũng-là-cách-demo)
   - [Cách 2: Chế độ phát triển (sửa giao diện)](#cách-2-chế-độ-phát-triển-sửa-giao-diện)
   - [Truy cập từ máy khác / điện thoại](#-truy-cập-từ-máy-khác--điện-thoại)
   - [Cách kiểm thử bằng Video có sẵn](#cách-kiểm-thử-bằng-video-có-sẵn)
5. [Quy Chuẩn AI & Phát Hiện Hành Vi](#-quy-chuẩn-ai--phát-hiện-hành-vi)
6. [Hướng Dẫn Đẩy Code Lên GitHub](#-hướng-dẫn-đẩy-code-lên-github)
   - [Quy trình đẩy bản mới nhất](#1-quy-trình-đẩy-bản-mới-nhất-hằng-ngày)
   - [Xử lý khi bị lỗi xung đột (Conflict / Rejected)](#2-xử-lý-khi-gặp-xung-đột-conflict--rejected)

---

## 🌟 Tính Năng Nổi Bật

- **Theo dõi từng thí sinh**: YOLO11-Pose (khung người + 17 điểm khớp) + ByteTrack; **số ghế cố định** khi bị che khuất (FT-01).
- **Phát hiện hành vi**: quay đầu nhìn bài (FT-02), dùng điện thoại (FT-07), cúi gập dưới bàn (FT-03), so với mốc riêng từng người.
- **Mô hình nhóm huấn luyện**: `turn_cls` (YOLO11s-cls) phân loại quay đầu trên ảnh cắt từng thí sinh — xem [`training/`](training/README.md).
- **Điểm rủi ro 0–100 & thanh độ nhạy 1–5** (FT-04), áp dụng ngay trong phiên.
- **Clip bằng chứng 5 s trước + 5 s sau** mỗi cảnh báo (FT-06), **âm báo** (FT-11), **biên bản ca thi PDF** (FT-10).
- **Camera hoặc video tải lên**; đổi nguồn tự xoá trạng thái cũ và lấy mốc lại.
- **Thời gian thực**: ~28 khung/giây với lớp ~23 người trên RTX 4060 (chế độ hiệu năng); web gửi 10 khung/giây.

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
│   │       ├── seats.py          # Số ghế cố định (FT-01)
│   │       ├── evidence.py       # Clip bằng chứng (FT-06)
│   │       └── pnp_head_pose.py  # Hàm góc (chuẩn hoá ±180°)
│   ├── models/                   # turn_cls.pt (nhóm train, có sẵn); yolo11l-pose.pt, yolo11m.pt tự tải
│   ├── requirements.txt
│   └── Dockerfile
│
├── training/                     # Chuẩn bị dữ liệu, train, đánh giá (xem training/README.md)
│   └── results/                  # Nhật ký 10 vòng cải thiện, bảng đánh giá, biểu đồ train
│
├── tools/
│   ├── benchmark.py              # Đo tốc độ pipeline (ms/khung, FPS) trên một video
│   └── render_demo.py            # Render video demo từ pipeline thật
├── scripts/
│   ├── start_backend.sh          # Khởi động backend (macOS/Linux)
│   ├── start-ai-server.sh        # Backend + Cloudflare Tunnel (tuỳ chọn, link công khai)
│   ├── start_tunnel.sh           # Chỉ mở Cloudflare Tunnel
│   └── run_tests.sh              # Chạy bộ kiểm thử tự động
├── package.json                  # Scripts quản lý toàn bộ workspace
├── README.md                     # Tài liệu hướng dẫn sử dụng
└── .gitignore                    # Loại trừ file rác, weights nặng & token bí mật
```

---

## 💻 Yêu Cầu Hệ Thống

- **Hệ điều hành**: Windows, macOS hoặc Linux. Nên có GPU NVIDIA (CUDA) để chạy thời gian thực; CPU vẫn chạy nhưng chậm.
- **Node.js**: Phiên bản 18.x trở lên (`node -v`).
- **Python**: 3.10 – 3.13 (`python --version`).
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

### Cách 1: Một máy chủ (khuyên dùng, cũng là cách demo)

Backend phục vụ luôn giao diện đã build, chỉ cần một tiến trình:

```bash
cd frontend && npm run build && cd ..
cd backend
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Mở **http://localhost:8000**, bấm **Tải video** hoặc **Bật camera**. Kiểm tra máy chủ: `http://localhost:8000/health`,
`http://localhost:8000/ready` (đã có model pose chưa), tài liệu API: `http://localhost:8000/docs`.
Trên macOS/Linux có thể dùng `bash scripts/start_backend.sh` (tự tạo venv, cài thư viện, tải model).

---

### Cách 2: Chế độ phát triển (sửa giao diện)

```bash
# Terminal 1 — backend, tự nạp lại khi sửa code Python
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Terminal 2 — giao diện có hot-reload
npm run dev
```

Mở **http://localhost:5173** (giao diện tự kết nối tới backend ở cổng 8000).

---

### 📱 Truy cập từ máy khác / điện thoại

- **Cùng mạng LAN, dùng video**: mở `http://<IP-máy-chủ>:8000` trên máy khác.
- **Camera trên điện thoại / máy Mac** chỉ bật được qua **HTTPS**: chạy uvicorn với chứng chỉ
  (`--ssl-keyfile key.pem --ssl-certfile cert.pem`, chứng chỉ tự ký thì trình duyệt sẽ cảnh báo, bấm tiếp tục).
- **Link công khai (tuỳ chọn)**: `npm run ai-server` mở Cloudflare Quick Tunnel dạng `https://xxxx.trycloudflare.com`;
  ai có link đều vào được, nên chỉ bật khi demo và đổi `DEMO_ACCESS_CODE` trong `backend/.env`.
  Dán link vào **⚙️ Cài Đặt → Địa chỉ AI Backend** nếu giao diện chạy ở nơi khác (vd Vercel).

---

### 🎥 Cách kiểm thử bằng Video có sẵn

Nếu không có webcam hoặc muốn thử nghiệm các tình huống quay cóp mẫu:
1. Nhấn nút **"📁 Tải Video Lên"** ngay cạnh nút Bật Camera.
2. Chọn video định dạng `.mp4`, `.mov` hoặc `.webm`.
3. Trình phát sẽ tự động trích xuất từng khung hình và truyền qua AI WebSocket để phân tích thời gian thực giống hệt như camera trực tiếp.

---

## 🎯 Quy Chuẩn AI & Phát Hiện Hành Vi

Mỗi khung hình (960 px, ~35 ms ở chế độ hiệu năng trên RTX 4060) đi qua 3 model: **YOLO11-Pose** tìm thí sinh + 17 điểm khớp,
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
  Có ngưỡng trễ: bắt đầu tính khi tín hiệu làm mượt > 0.35, chỉ dừng khi < 0.2, nên detector sót 1–2 khung không làm đếm lại.
- **Cúi người (BENDING)**: chỉ là nhãn đi kèm, không tự gây cảnh báo (cúi viết bài là bình thường).
- **Cúi gập nhìn dưới bàn (UNDER_DESK, FT-03)**: đỉnh đầu (mép trên khung người) hạ $\ge 0.5$ lần độ rộng vai so với mốc,
  kéo dài $\ge 3$ giây — vẫn đánh giá được khi mặt bị che. Chỉ áp dụng khi người đủ lớn (vai $\ge 9\%$ chiều rộng ảnh).
  DS-03: người viết bài bình thường đầu hạ tối đa 0.14 vai.
- **Điểm rủi ro & độ nhạy (FT-04)**: điểm 0–100 = số giây có hành vi nghi vấn trong **30 giây gần nhất**
  (5 giây = 100 điểm). Thanh **Độ nhạy** 1–5 trên giao diện (mặc định 3) đổi thời gian cần kéo dài trước khi cảnh báo
  (quay đầu: 3 s … 0.75 s), áp dụng ngay qua WebSocket.
- **Số ghế cố định (FT-01)**: mỗi vị trí ngồi có số ghế; khi bộ theo dõi đổi ID (bị che khuất), ID mới ở đúng chỗ đó
  vẫn mang số ghế cũ. Người có khung khác hẳn kích thước (đứng / đi lại, vd giám thị) không nhận ghế của người ngồi.
- **Biên bản ca thi (FT-10)**: nút **Biên bản** mở trang in A4 (thí sinh xếp theo điểm nghi vấn, danh sách sự kiện,
  quyết định giám thị, link clip, chỗ ký) → chọn "Lưu dưới dạng PDF". Vẫn có xuất CSV / JSON.
- **Clip bằng chứng (FT-06)**: mỗi sự kiện REVIEW mới tự lưu clip MP4 (H.264) gồm 5 giây trước + 5 giây sau, thí sinh
  bị khoanh đỏ, vào `backend/evidence/<phiên>/<sự kiện>.mp4` (tối đa 50 clip/phiên). Xem bằng nút **Clip** trong
  "Nhật Ký Sự Kiện" hoặc API `GET /api/sessions/{session_id}/evidence/{event_id}` (`.../status` để biết đã ghi xong chưa).
- **Âm báo (FT-11)**: kêu 2 tiếng bíp khi bảng "Nhật Ký Sự Kiện" có sự kiện nghi vấn mới (không kêu lặp cho thí sinh
  đang có sự kiện chờ xử lý). Nút **Âm báo / Tắt tiếng** ở đầu bảng, trình duyệt nhớ lựa chọn.
- **Chế độ hiệu năng (MS-02)**: pose + theo dõi chạy mọi khung; turn_cls và detector điện thoại mỗi model chạy 1/3 số khung,
  so le nhau, khung còn lại dùng kết quả gần nhất (`AUX_MODEL_EVERY_N=3`, đặt `1` để chạy mọi khung).
  Lớp đông người trên RTX 4060, ảnh 960 px: 53 → 35 ms/khung (18.8 → **~28,5 FPS**), kết quả đánh giá không giảm.
  Đo lại: `python tools/benchmark.py --video <video>`.

Kết quả trên tập test DS-03 (sinh viên 5–8, không dùng để chỉnh): nhìn bài bạn 4/4, điện thoại 6/8,
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
