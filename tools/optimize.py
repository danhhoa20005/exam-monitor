"""
optimize.py - YOLOv8 Model ONNX / CoreML Optimization Export
"""
import os
import time
from ultralytics import YOLO


def get_file_size(path):
    return round(os.path.getsize(path) / (1024 * 1024), 2)


def main():
    model_path = "backend/models/best.pt"
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return

    print("=" * 50)
    print("MODEL OPTIMIZATION - ONNX EXPORT")
    print("=" * 50)

    model = YOLO(model_path)
    start = time.time()
    export_path = model.export(format="onnx", imgsz=640, simplify=True)
    elapsed = time.time() - start
    print(f"Export completed in {elapsed:.1f}s -> {export_path}")


if __name__ == "__main__":
    main()
