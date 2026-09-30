"""
benchmark.py - Compare PyTorch vs Exported Model Performance
"""
import time
import os
import numpy as np
from ultralytics import YOLO


def get_file_size(path):
    if os.path.isdir(path):
        total = sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
        return round(total / (1024 * 1024), 2)
    return round(os.path.getsize(path) / (1024 * 1024), 2)


def measure_fps(model, num_frames=30):
    dummy = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    for _ in range(5):
        model.predict(dummy, verbose=False)

    start = time.time()
    for _ in range(num_frames):
        model.predict(dummy, verbose=False)
    elapsed = time.time() - start

    fps = num_frames / elapsed
    avg_ms = (elapsed / num_frames) * 1000
    return round(fps, 1), round(avg_ms, 1)


def main():
    pt_path = "backend/models/best.pt"
    if not os.path.exists(pt_path):
        print(f"ERROR: Model not found at {pt_path}")
        return

    print("=" * 60)
    print("BENCHMARK: VisionGuard YOLOv8-nano Performance")
    print("=" * 60)

    pt_model = YOLO(pt_path)
    pt_size = get_file_size(pt_path)
    pt_fps, pt_ms = measure_fps(pt_model)

    print(f"Model Path:     {pt_path}")
    print(f"Model Size:     {pt_size} MB")
    print(f"Inference FPS:  {pt_fps} FPS")
    print(f"Latency:        {pt_ms} ms / frame")
    print(f"Classes:        {pt_model.names}")
    print("=" * 60)


if __name__ == "__main__":
    main()
