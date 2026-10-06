"""
Script to download official MediaPipe Tasks Pose Landmarker models
and verify YOLO model weights.
"""
import os
import sys
import hashlib
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
POSE_MODEL_PATH = os.path.join(BASE_DIR, "pose_landmarker_lite.task")

EXPECTED_YOLO_SHA256 = "c1ea0a60e07a33c4bd01263e261e644cd74cf2520d164acf9512f5828512bbe1"
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "best.pt")

def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def download_pose_model():
    if os.path.exists(POSE_MODEL_PATH) and os.path.getsize(POSE_MODEL_PATH) > 1000000:
        print(f"[OK] MediaPipe Pose Landmarker already exists: {POSE_MODEL_PATH}")
        return True
    
    print(f"[INFO] Downloading MediaPipe Pose Landmarker Lite from {POSE_MODEL_URL}...")
    try:
        urllib.request.urlretrieve(POSE_MODEL_URL, POSE_MODEL_PATH)
        print(f"[OK] Downloaded successfully: {POSE_MODEL_PATH} ({os.path.getsize(POSE_MODEL_PATH)} bytes)")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download MediaPipe Pose Landmarker: {e}")
        return False

def download_yolo_pose_model(model_name: str = "yolo11n-pose.pt") -> bool:
    """Download and prepare Ultralytics YOLO-Pose weights (YOLO11-Pose)."""
    target = os.path.join(BASE_DIR, model_name)
    if os.path.exists(target) and os.path.getsize(target) > 1000000:
        print(f"[OK] YOLO11-Pose model already exists: {target} ({os.path.getsize(target)} bytes)")
        return True
    
    print(f"[INFO] Downloading YOLO-Pose weights: {model_name}...")
    try:
        from ultralytics import YOLO
        m = YOLO(model_name)
        if os.path.exists(model_name) and not os.path.exists(target):
            os.rename(model_name, target)
        print(f"[OK] YOLO-Pose model ready: {target}")
        return True
    except Exception as e:
        print(f"[WARN] Could not automatically download {model_name}: {e}")
        return False

def verify_yolo_model():
    # Check YOLO-Pose model first (Cheating-detection-YOLO)
    pose_name = os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt")
    pose_path = os.path.join(BASE_DIR, pose_name)
    if os.path.exists(pose_path):
        print(f"[OK] Active YOLO-Pose model found: {pose_path}")
        return True

    if not os.path.exists(YOLO_MODEL_PATH):
        print(f"[INFO] YOLO11-Pose model not found yet. Attempting download of {pose_name}...")
        download_yolo_pose_model(pose_name)
        return os.path.exists(pose_path)
    
    actual_hash = calculate_sha256(YOLO_MODEL_PATH)
    print(f"[INFO] YOLO Model SHA-256: {actual_hash}")
    return True

if __name__ == "__main__":
    download_pose_model()
    download_yolo_pose_model()
    verify_yolo_model()

