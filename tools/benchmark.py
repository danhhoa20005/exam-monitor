"""
benchmark.py - Benchmark YOLO Detection & Pose Inference Performance
Measures inference FPS, latency per frame, and memory footprint.

Usage:
    python tools/benchmark.py
    python tools/benchmark.py --model backend/models/yolo11l-pose.pt --frames 50
"""
import os
import sys
import time
import argparse
import numpy as np
from ultralytics import YOLO


def resolve_model_path(user_model_path=None):
    """Find the best available model path regardless of current working directory."""
    if user_model_path and os.path.exists(user_model_path):
        return user_model_path

    # Candidate directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    
    candidates = [
        user_model_path,
        os.path.join(project_root, "backend", "models", "yolo11l-pose.pt"),
        os.path.join(project_root, "backend", "models", "yolo11s-pose.pt"),
        os.path.join(project_root, "backend", "models", "yolo11n-pose.pt"),
        os.path.join(project_root, "backend", "models", "best.pt"),
        os.path.join(project_root, "backend", "models", "yolov8n.pt"),
        "backend/models/yolo11l-pose.pt",
        "backend/models/yolo11n-pose.pt",
        "backend/models/best.pt",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def get_file_size(path):
    if os.path.isdir(path):
        total = sum(
            os.path.getsize(os.path.join(path, f))
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
        )
        return round(total / (1024 * 1024), 2)
    return round(os.path.getsize(path) / (1024 * 1024), 2)


def measure_fps(model, num_frames=30, img_size=640):
    dummy = np.random.randint(0, 255, (img_size, img_size, 3), dtype=np.uint8)
    # Warmup runs
    for _ in range(5):
        model.predict(dummy, verbose=False)

    start = time.time()
    for _ in range(num_frames):
        model.predict(dummy, verbose=False)
    elapsed = time.time() - start

    fps = num_frames / max(1e-6, elapsed)
    avg_ms = (elapsed / num_frames) * 1000
    return round(fps, 1), round(avg_ms, 1)


def main():
    parser = argparse.ArgumentParser(description="Benchmark YOLO Performance")
    parser.add_argument("--model", type=str, default=None, help="Path to model weights (.pt)")
    parser.add_argument("--frames", type=int, default=30, help="Number of test frames to evaluate")
    parser.add_argument("--size", type=int, default=640, help="Frame resolution size (default: 640)")
    args = parser.parse_args()

    pt_path = resolve_model_path(args.model)
    if not pt_path:
        print("ERROR: No model weights found.")
        print("Please specify a model path with --model or download one using:")
        print("  python backend/models/download_models.py")
        sys.exit(1)

    print("=" * 64)
    print("BENCHMARK: VisionGuard AI YOLO Model Performance")
    print("=" * 64)

    try:
        pt_model = YOLO(pt_path)
    except Exception as e:
        print(f"ERROR: Failed to load YOLO model at {pt_path}: {e}")
        sys.exit(1)

    pt_size = get_file_size(pt_path)
    pt_fps, pt_ms = measure_fps(pt_model, num_frames=args.frames, img_size=args.size)

    task_name = getattr(pt_model, 'task', 'detect')
    classes = getattr(pt_model, 'names', {})

    print(f"Model Path:     {pt_path}")
    print(f"Model Size:     {pt_size} MB")
    print(f"Model Task:     {task_name}")
    print(f"Inference FPS:  {pt_fps} FPS (Tested on {args.frames} frames @ {args.size}x{args.size})")
    print(f"Latency:        {pt_ms} ms / frame")
    print(f"Classes:        {classes}")
    print("=" * 64)


if __name__ == "__main__":
    main()
