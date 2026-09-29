# Thư mục chứa trọng số mô hình AI (Models Directory)

## 1. Trọng số YOLOv8s đã huấn luyện (`best.pt`)

Sao chép file model `best.pt` của bạn vào thư mục này:
```text
backend/models/best.pt
```

### Checksum SHA-256 tiêu chuẩn theo đặc tả:
```text
c1ea0a60e07a33c4bd01263e261e644cd74cf2520d164acf9512f5828512bbe1
```

Kiểm tra mã băm SHA-256 trên macOS:
```bash
shasum -a 256 backend/models/best.pt
```

Hoặc chạy script tự động kiểm tra:
```bash
python3 backend/models/download_models.py
```

---

## 2. Mô hình MediaPipe Tasks Pose Landmarker

File `pose_landmarker_lite.task` sẽ được tự động tải về khi chạy:
```bash
python3 backend/models/download_models.py
```
Hoặc khi khởi động server FastAPI.
