"""
optimize.py - YOLO Model Optimization & Export (ONNX / TorchScript / CoreML)
"""
import os
import sys
import time
import argparse
from ultralytics import YOLO


def resolve_model_path(user_model_path=None):
    if user_model_path and os.path.exists(user_model_path):
        return user_model_path

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    
    candidates = [
        user_model_path,
        os.path.join(project_root, "backend", "models", "yolo11n-pose.pt"),
        os.path.join(project_root, "backend", "models", "yolo11s-pose.pt"),
        os.path.join(project_root, "backend", "models", "yolo11l-pose.pt"),
        os.path.join(project_root, "backend", "models", "best.pt"),
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


def main():
    parser = argparse.ArgumentParser(description="Optimize & Export YOLO Weights")
    parser.add_argument("--model", type=str, default=None, help="Path to input .pt weights")
    parser.add_argument("--format", type=str, default="onnx", choices=["onnx", "torchscript", "coreml", "openvino"], help="Target export format")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    args = parser.parse_args()

    model_path = resolve_model_path(args.model)
    if not model_path:
        print("ERROR: Model not found. Specify with --model path/to/model.pt")
        sys.exit(1)

    print("=" * 60)
    print(f"MODEL OPTIMIZATION — EXPORT TO {args.format.upper()}")
    print("=" * 60)
    print(f"Source Model: {model_path} ({get_file_size(model_path)} MB)")

    try:
        model = YOLO(model_path)
        start = time.time()
        export_path = model.export(format=args.format, imgsz=args.imgsz, simplify=True)
        elapsed = time.time() - start
        print(f"Export completed in {elapsed:.1f}s -> {export_path}")
    except Exception as e:
        print(f"Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
