# Trọng số mô hình (`backend/models/`)

| File | Vai trò | Nguồn |
|---|---|---|
| `yolo11l-pose.pt` | Tìm thí sinh + 17 điểm khớp | Ultralytics (COCO), **tự tải** lần chạy đầu |
| `yolo11m.pt` | Phát hiện điện thoại (lớp `cell phone`) | Ultralytics (COCO), **tự tải** lần chạy đầu |
| `turn_cls.pt` | Phân loại quay đầu trên ảnh cắt từng thí sinh | **Nhóm huấn luyện** (`training/train_turn_cls.py`), có sẵn trong repo |

Tải trước (vd máy demo không có Internet lúc thuyết trình):

```bash
cd backend
python models/download_models.py
```

Đổi hoặc tắt model bằng biến môi trường: `YOLO_POSE_MODEL`, `PHONE_MODEL`, `TURN_CLS_MODEL`
(`none.pt` = tắt). Các file `.pt` khác trong thư mục này bị `.gitignore` bỏ qua, trừ `turn_cls.pt`.
