"""
Download the pretrained Ultralytics weights the backend uses (first run needs Internet):
    yolo11l-pose.pt  person boxes + 17 keypoints   (env YOLO_POSE_MODEL)
    yolo11m.pt       COCO 'cell phone' detector     (env PHONE_MODEL, "none.pt" = off)
turn_cls.pt (the team-trained head-turn classifier) is already in this folder.

    python models/download_models.py
"""
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def download_yolo_pose_model(model_name: str = "yolo11l-pose.pt") -> bool:
    """Fetch an Ultralytics weights file by name into this folder (any model, not only pose)."""
    target = os.path.join(BASE_DIR, model_name)
    if os.path.exists(target) and os.path.getsize(target) > 1000000:
        print(f"[OK] {model_name} already present ({os.path.getsize(target)} bytes)")
        return True
    print(f"[INFO] Downloading {model_name}...")
    try:
        from ultralytics import YOLO
        YOLO(model_name)                       # Ultralytics downloads into the working directory
        if os.path.exists(model_name) and not os.path.exists(target):
            os.replace(model_name, target)
        print(f"[OK] {model_name} ready: {target}")
        return True
    except Exception as e:
        print(f"[WARN] Could not download {model_name}: {e}")
        return False


def required_models():
    names = [os.getenv("YOLO_POSE_MODEL", "yolo11l-pose.pt")]
    phone = os.getenv("PHONE_MODEL", "yolo11m.pt")
    if phone.lower() != "none.pt":
        names.append(phone)
    return names


def ensure_models() -> bool:
    """Download whatever is missing; True when every required model is present."""
    return all([download_yolo_pose_model(n) for n in required_models()])


if __name__ == "__main__":
    ensure_models()
