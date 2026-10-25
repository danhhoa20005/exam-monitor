"""
Configuration settings and algorithm thresholds for VisionGuard AI Backend.
Specification Version: 1.0.0 (2026-09-27)
"""
import os
from pathlib import Path
try:
    from pydantic_settings import BaseSettings
    from pydantic import field_validator
except ImportError:
    from pydantic import BaseModel as BaseSettings
    field_validator = None

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "VisionGuard AI Posture Monitor Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    if field_validator is not None:
        @field_validator("DEBUG", mode="before")
        @classmethod
        def parse_debug(cls, value):
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on", "debug", "development"}
            return value
    
    # Server & Security
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = os.getenv("SECRET_KEY", "exam-monitor-secret-key-2026-secure-token")
    DEMO_ACCESS_CODE: str = os.getenv("DEMO_ACCESS_CODE", "demo2026")
    WS_TICKET_EXPIRE_SECONDS: int = 300  # 5 minutes
    
    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
        "https://*.trycloudflare.com"
    ]
    
    # Paths
    MODELS_DIR: Path = BASE_DIR / "models"
    CONFIG_DIR: Path = BASE_DIR / "config"
    YOLO_POSE_MODEL_PATH: Path = BASE_DIR / "models" / os.getenv("YOLO_POSE_MODEL", "yolo11l-pose.pt")
    # 960 finds ~23 of the students in a 720p classroom shot vs ~16 at 640 (yolo11l-pose, ~22ms on RTX 4060)
    YOLO_IMGSZ: int = int(os.getenv("YOLO_IMGSZ", "960"))
    YOLO_CONF: float = float(os.getenv("YOLO_CONF", "0.25"))
    YOLO_MODEL_PATH: Path = BASE_DIR / "models" / "best.pt"
    # Optional team-trained turn/normal crop classifier (training/train_turn_cls.py); skipped if the file is absent
    TURN_CLS_MODEL_PATH: Path = BASE_DIR / "models" / os.getenv("TURN_CLS_MODEL", "turn_cls.pt")
    TURN_CLS_EMA_ALPHA: float = float(os.getenv("TURN_CLS_EMA_ALPHA", "0.3"))   # per-track smoothing at ~10 FPS
    TURN_CLS_THRESHOLD: float = float(os.getenv("TURN_CLS_THRESHOLD", "0.8"))   # smoothed P(turn) counted as turning
    TURN_CLS_MARGIN: float = float(os.getenv("TURN_CLS_MARGIN", "0.5"))         # ...and this far above the student's own baseline

    # Phone use: COCO detector 'cell phone' (class 67) next to a wrist keypoint, sustained.
    # DS-03 dev: phone within 0.5 shoulder widths of a wrist in >=30% of frames for 7/9 phone users, 0/17 normal.
    PHONE_MODEL_PATH: Path = BASE_DIR / "models" / os.getenv("PHONE_MODEL", "yolo11m.pt")
    # highest detector confidence that keeps DS-03 dev phone recall (7/9); 0.2 let thick pens pass as phones
    PHONE_CONF: float = float(os.getenv("PHONE_CONF", "0.3"))
    PHONE_NEAR_WRIST_SW: float = 0.5        # max phone-centre to wrist distance, in shoulder widths
    # DS-03 dev box shape: phones area/shoulder_w^2 p90 0.043, aspect p10 1.7; pen-holding fists area p10 0.053, aspect p50 1.1
    PHONE_MAX_AREA_SW2: float = 0.05
    PHONE_MIN_ASPECT: float = 1.3
    PHONE_EMA_ALPHA: float = 0.3            # per-track smoothing of the per-frame "phone in hand" flag
    PHONE_EMA_ON: float = 0.35              # smoothed flag above this counts as holding a phone
    PHONE_TRIGGER_S: float = float(os.getenv("PHONE_TRIGGER_S", "1.0"))
    FALLBACK_YOLO_PATH: Path = BASE_DIR / "models" / "yolov8s.pt"
    POSE_MODEL_PATH: Path = BASE_DIR / "models" / "pose_landmarker_lite.task"
    BYTETRACK_CONFIG_PATH: Path = BASE_DIR / "config" / "bytetrack.yaml"
    
    # Expected Weights Checksum (SHA-256)
    EXPECTED_YOLO_SHA256: str = "c1ea0a60e07a33c4bd01263e261e644cd74cf2520d164acf9512f5828512bbe1"
    
    # Algorithm Rules & Thresholds (dyingangell/Cheating-detection-YOLO)
    CALIBRATION_SAMPLES: int = 20              # 20 consecutive valid pose samples per ID
    YAW_THRESHOLD_DEG: float = 35.0            # abs(delta_yaw) > 35.0 degrees
    NOSE_DROP_RATIO_THRESHOLD: float = 0.15    # nose_y - nose_y_0 > 0.15 * frame_height
    REVIEW_TRIGGER_DURATION_S: float = 1.5     # Continuous duration >= 1.5s
    GAP_RESET_TIMEOUT_S: float = 2.5           # Gap > 2.5s resets behavior timer
    LANDMARK_MIN_VISIBILITY: float = 0.30      # Minimum keypoint confidence
    ROI_EXPAND_RATIO: float = 0.12             # Expand student ROI box by 12%

    # Cheating-detection-YOLO Enhanced Parameters
    POSE_BASE_RADIUS: float = float(os.getenv("POSE_BASE_RADIUS", "0.38"))
    POSE_FORESHORTENING_STRENGTH: float = float(os.getenv("POSE_FORESHORTENING_STRENGTH", "0.4"))
    POSE_WARN_THRESHOLD_S: float = float(os.getenv("POSE_WARN_THRESHOLD_S", "3.0"))
    POSE_CALIB_S: float = float(os.getenv("POSE_CALIB_S", "10.0"))
    POSE_MAX_AWAY_DIST: float = float(os.getenv("POSE_MAX_AWAY_DIST", "2.0"))
    POSE_WALK_PX: float = float(os.getenv("POSE_WALK_PX", "30.0"))
    POSE_SCORE_K: float = float(os.getenv("POSE_SCORE_K", "1.0"))
    POSE_ANGLE_BASE_RAD: float = float(os.getenv("POSE_ANGLE_BASE_RAD", "0.45"))
    POSE_ANGLE_WEIGHT: float = float(os.getenv("POSE_ANGLE_WEIGHT", "0.0"))
    POSE_DEPTH_SUPPRESS_RATIO: float = float(os.getenv("POSE_DEPTH_SUPPRESS_RATIO", "1.5"))
    
    # Performance & Concurrency Limits
    MAX_CONCURRENT_SESSIONS: int = 1           # MVP single active inference session
    MAX_QUEUE_SIZE: int = 2                    # Max pending frames queue
    MAX_MESSAGE_BYTES: int = 1048576           # 1 MB max WS frame payload
    
    class Config:
        env_file = (str(BASE_DIR / ".env"), ".env")
        extra = "ignore"

settings = Settings()
