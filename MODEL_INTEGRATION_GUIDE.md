# HƯỚNG DẪN GHÉP NỐI AI MODEL (YOLOv8 + ByteTrack + MediaPipe) VÀO FRONTEND

Tài liệu này cung cấp chi tiết chuẩn giao thức WebSocket và ví dụ code Backend Python (FastAPI) để kết nối trực tiếp với Frontend React/Vite.

---

## 1. TỔNG QUAN LUỒNG DỮ LIỆU

```text
[Điện thoại / Trình duyệt] 
       │
       │ (1) Mở Camera (Ưu tiên Camera sau hoặc Camera trước)
       │ (2) Gửi Frame JPEG base64 qua WebSocket (5 - 10 FPS)
       ▼
[Backend AI (Python FastAPI)]
       │
       ├─► (3) YOLOv8 Detect Người / Thí sinh
       ├─► (4) ByteTrack Theo dõi Track ID liên tục
       ├─► (5) MediaPipe BlazePose Trích xuất góc lệch đầu (Yaw) & độ hạ mũi
       └─► (6) Phân loại 5 trạng thái tư thế (CALIBRATING, WITHIN_THRESHOLDS, OBSERVING, REVIEW, POSE_UNAVAILABLE)
       │
       ▼ (7) Trả JSON danh sách Bounding Boxes & Telemetry về
[Frontend React / Canvas Overlay]
       │
       └─► Vẽ Bounding Box, màu trạng thái, nhãn nghi vấn, hiển thị bảng giám thị.
```

---

## 2. CHUẨN GIAO THỨC WEBSOCKET (PROTOCOL SPECIFICATION)

### A. Client gửi lên Server (Frontend -> Backend):

**Endpoint:** `ws://<HOST>:<PORT>/ws/sessions/{session_id}`

#### 1. Tin nhắn xác thực khởi tạo (Auth Message):
```json
{
  "type": "auth",
  "ws_ticket": "demo-ticket-2026",
  "session_id": "session-local-01",
  "client_timestamp": 1727581200000
}
```

#### 2. Tin nhắn Frame Camera (Frame Message - gửi mỗi 100ms - 200ms):
```json
{
  "type": "frame",
  "frame_id": 1727581200100,
  "session_id": "session-local-01",
  "captured_at_ms": 1727581200100,
  "width": 640,
  "height": 480,
  "facing_mode": "environment", // "environment" (Cam sau) hoặc "user" (Cam trước)
  "jpeg_base64": "/9j/4AAQSkZJRgABAQEASABIAAD..."
}
```

---

### B. Server trả về Frontend (Backend -> Frontend):

#### Tin nhắn kết quả phân tích tư thế (Result Message):
```json
{
  "type": "result",
  "session_id": "session-local-01",
  "frame_id": 1727581200100,
  "captured_at_ms": 1727581200100,
  "processing_ms": 35,
  "frame_size": [640, 480],
  "tracks": [
    {
      "track_id": 1,
      "bbox_xyxy_norm": [0.18, 0.15, 0.42, 0.72],
      "detection_confidence": 0.94,
      "pose_valid": true,
      "calibration_samples": 20,
      "status": "WITHIN_THRESHOLDS",
      "reasons": [],
      "yaw_delta_deg": 3.5,
      "nose_drop_ratio": 0.02,
      "turning_duration_ms": 0,
      "bending_duration_ms": 0
    },
    {
      "track_id": 2,
      "bbox_xyxy_norm": [0.55, 0.20, 0.85, 0.78],
      "detection_confidence": 0.91,
      "pose_valid": true,
      "calibration_samples": 20,
      "status": "REVIEW",
      "reasons": ["Quay đầu liên tục (>35°)"],
      "yaw_delta_deg": 42.1,
      "nose_drop_ratio": 0.04,
      "turning_duration_ms": 1800,
      "bending_duration_ms": 0
    }
  ],
  "new_event_ids": ["evt-1727581200100-2"]
}
```

---

## 3. 5 TRẠNG THÁI TƯ THẾ (TRACK STATUS)

1. **`CALIBRATING`** (Màu Xanh Dương `#3b82f6`):
   - Thí sinh đang trong 20 frame đầu tiên để hệ thống ghi nhận tư thế chuẩn làm mốc tham chiếu (`calibration_samples: 0..20`).
2. **`WITHIN_THRESHOLDS`** (Màu Xanh Lá `#10b981`):
   - Tư thế bình thường, độ lệch góc quay đầu $\le 35^\circ$ và độ hạ mũi $\le 15\%$.
3. **`OBSERVING`** (Màu Vàng Hổ Phách `#f59e0b`):
   - Thí sinh có góc quay đầu $> 35^\circ$ hoặc hạ mũi $> 15\%$, nhưng thời gian duy trì $< 1.5$ giây.
4. **`REVIEW`** (Màu Đỏ `#ef4444`):
   - Tư thế bất thường kéo dài $\ge 1.5$ giây. Hệ thống tạo event nghi vấn để giám thị xem xét.
5. **`POSE_UNAVAILABLE`** (Màu Xám `#64748b`):
   - Đối tượng bị che khuất một phần hoặc không nhận diện đủ các điểm mốc MediaPipe (mũi, tai, mắt).

---

## 4. VÍ DỤ BACKEND PYTHON FASTAPI (MẪU KHỞI TẠO)

Bạn có thể tạo file `backend_server.py` để chạy thử nghiệm với Frontend:

```python
import base64
import io
import time
import json
import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Exam Monitor AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    print(f"[*] Client connected to session: {session_id}")
    
    try:
        while True:
            text_data = await websocket.receive_text()
            message = json.loads(text_data)
            
            if message.get("type") == "auth":
                print(f"[Auth] Client authenticated: {message.get('ws_ticket')}")
                continue
                
            if message.get("type") == "frame":
                t_start = time.time()
                
                # 1. Giải mã JPEG Base64
                img_bytes = base64.b64decode(message["jpeg_base64"])
                image = Image.open(io.BytesIO(img_bytes))
                cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # 2. ĐƯA VÀO MODEL AI CỦA BẠN (YOLOv8 + ByteTrack + MediaPipe)
                # results = yolo_model(cv_img)
                # tracks = tracker.update(results)
                # poses = mediapipe_pose(cv_img)
                
                processing_time_ms = int((time.time() - t_start) * 1000)
                
                # 3. Trả về kết quả JSON theo chuẩn Frontend
                response_payload = {
                    "type": "result",
                    "session_id": session_id,
                    "frame_id": message.get("frame_id"),
                    "captured_at_ms": message.get("captured_at_ms"),
                    "processing_ms": processing_time_ms,
                    "frame_size": [message.get("width", 640), message.get("height", 480)],
                    "tracks": [
                        {
                            "track_id": 1,
                            "bbox_xyxy_norm": [0.25, 0.15, 0.75, 0.85],
                            "detection_confidence": 0.95,
                            "pose_valid": True,
                            "calibration_samples": 20,
                            "status": "WITHIN_THRESHOLDS",
                            "reasons": [],
                            "yaw_delta_deg": 2.1,
                            "nose_drop_ratio": 0.01
                        }
                    ],
                    "new_event_ids": []
                }
                
                await websocket.send_text(json.dumps(response_payload))
                
    except WebSocketDisconnect:
        print(f"[-] Client disconnected from session: {session_id}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 5. THỬ NGHIỆM TRÊN GIAO DIỆN WEB

1. Mở giao diện Web tại `http://localhost:5173`.
2. Bấm vào nút **"Ghép Model"** trên thanh Header.
3. Chọn chế độ **"Live AI Model (WebSocket)"**.
4. Nhập URL WebSocket `ws://127.0.0.1:8000/ws/sessions/session-01` và bấm **"Lưu Cấu Hình"**.
5. Bấm **"Mở Camera"** để bắt đầu truyền frame realtime!
