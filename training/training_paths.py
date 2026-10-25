"""
Đường dẫn dùng chung cho mọi script train / đánh giá.

Dataset, model train ra và kết quả đánh giá đều nằm trong TRAINING_WORKDIR
(mặc định: training/workspace, đã nằm trong .gitignore vì nặng vài GB).
Muốn dùng dữ liệu đã có sẵn ở chỗ khác, đặt biến môi trường, vd trên Windows:
    $env:TRAINING_WORKDIR = "D:/HTTM"
Cấu trúc bên trong TRAINING_WORKDIR:
    dataset/   dữ liệu (raw + đã chia train/val/test)
    models/    kết quả các lần train (weights, biểu đồ)
    result/    kết quả đánh giá / video chạy thử
    test/      video kiểm thử (vd classroom.mp4)
"""
import os
from pathlib import Path

TRAINING_DIR = Path(__file__).resolve().parent
REPO_DIR = TRAINING_DIR.parent
BACKEND_DIR = REPO_DIR / "backend"

WORK_DIR = Path(os.environ.get("TRAINING_WORKDIR", TRAINING_DIR / "workspace"))
DATASET_DIR = WORK_DIR / "dataset"
MODELS_DIR = WORK_DIR / "models"
RESULT_DIR = WORK_DIR / "result"
TEST_VIDEO = WORK_DIR / "test" / "classroom.mp4"

# Model pose dùng chung với backend (backend tự tải về ở lần chạy đầu)
POSE_MODEL = BACKEND_DIR / "models" / "yolo11l-pose.pt"
