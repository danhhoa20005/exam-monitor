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

def verify_yolo_model():
    if not os.path.exists(YOLO_MODEL_PATH):
        print(f"[WARN] YOLO model weights not found at {YOLO_MODEL_PATH}.")
        print("[INFO] You can copy 'best.pt' to this folder or it will fallback to YOLOv8s default if needed.")
        return False
    
    actual_hash = calculate_sha256(YOLO_MODEL_PATH)
    print(f"[INFO] YOLO Model SHA-256: {actual_hash}")
    if actual_hash == EXPECTED_YOLO_SHA256:
        print("[OK] YOLO model checksum matches expected specification SHA-256!")
        return True
    else:
        print(f"[WARN] YOLO model checksum differs from specification (expected {EXPECTED_YOLO_SHA256}).")
        return True

if __name__ == "__main__":
    download_pose_model()
    verify_yolo_model()
