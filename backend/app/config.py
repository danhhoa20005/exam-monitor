"""
Configuration settings and algorithm thresholds for VisionGuard AI Backend.
Specification Version: 1.0.0 (2026-09-27)
"""
import os
from pathlib import Path
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "VisionGuard AI Posture Monitor Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
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
    YOLO_MODEL_PATH: Path = BASE_DIR / "models" / "best.pt"
    FALLBACK_YOLO_PATH: Path = BASE_DIR / "models" / "yolov8s.pt"
    POSE_MODEL_PATH: Path = BASE_DIR / "models" / "pose_landmarker_lite.task"
    BYTETRACK_CONFIG_PATH: Path = BASE_DIR / "config" / "bytetrack.yaml"
    
    # Expected Weights Checksum (SHA-256)
    EXPECTED_YOLO_SHA256: str = "c1ea0a60e07a33c4bd01263e261e644cd74cf2520d164acf9512f5828512bbe1"
    
    # Algorithm Rules & Thresholds (As per Section 5.2 of Specification)
    CALIBRATION_SAMPLES: int = 20              # 20 consecutive valid pose samples per ID
    YAW_THRESHOLD_DEG: float = 35.0            # abs(delta_yaw) > 35.0 degrees
    NOSE_DROP_RATIO_THRESHOLD: float = 0.15    # nose_y - nose_y_0 > 0.15 * frame_height
    REVIEW_TRIGGER_DURATION_S: float = 1.5     # Continuous duration >= 1.5s
    GAP_RESET_TIMEOUT_S: float = 2.5           # Gap > 2.5s resets behavior timer
    LANDMARK_MIN_VISIBILITY: float = 0.5       # Minimum keypoint visibility score
    ROI_EXPAND_RATIO: float = 0.12             # Expand student ROI box by 12%
    
    # Performance & Concurrency Limits
    MAX_CONCURRENT_SESSIONS: int = 1           # MVP single active inference session
    MAX_QUEUE_SIZE: int = 2                    # Max pending frames queue
    MAX_MESSAGE_BYTES: int = 1048576           # 1 MB max WS frame payload
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
