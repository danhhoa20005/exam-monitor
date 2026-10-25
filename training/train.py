from multiprocessing import freeze_support
from ultralytics import YOLO

from training_paths import DATASET_DIR, MODELS_DIR


def main():
    DATA = f"{DATASET_DIR}/student/data.yaml"

    # YOLO26 Extra Large pretrained
    model = YOLO("yolo26x.pt")

    model.train(
        data=DATA,

        # ===== TRAIN =====
        epochs=100,
        imgsz=256,

        # Tự chọn batch để nhắm ~90% VRAM
        batch=0.90,

        # RTX 4060
        device=0,

        # ===== LOAD DATA =====
        workers=4,
        cache=False,

        # ===== TRAIN QUALITY =====
        patience=20,
        amp=True,

        optimizer="auto",
        cos_lr=True,
        close_mosaic=10,

        seed=42,

        # ===== OUTPUT =====
        project=f"{MODELS_DIR}",
        name="student_v3"
    )


if __name__ == "__main__":
    freeze_support()
    main()