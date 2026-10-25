from ultralytics import YOLO

from training_paths import MODELS_DIR, RESULT_DIR, TEST_VIDEO

MODEL_PATH = f"{MODELS_DIR}/student_v3/weights/best.pt"
VIDEO_PATH = str(TEST_VIDEO)

# Load model đã train
model = YOLO(MODEL_PATH)

# Test video
results = model.predict(
    source=VIDEO_PATH,

    conf=0.20,
    iou=0.50,
    imgsz=256,

    device=0,

    save=True,
    stream=True,
    verbose=True,

    project=f"{RESULT_DIR}",
    name="yolo26x_test",
    exist_ok=True
)

# stream=True nên phải duyệt hết kết quả
for _ in results:
    pass

print("\nĐã test xong.")
print("Video kết quả nằm tại:")
print(f"{RESULT_DIR}/yolo26x_test/")