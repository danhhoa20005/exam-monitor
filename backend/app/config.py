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
    PHONE_EMA_OFF: float = float(os.getenv("PHONE_EMA_OFF", "0.2"))   # ...until it drops below this (hysteresis)
    PHONE_TRIGGER_S: float = float(os.getenv("PHONE_TRIGGER_S", "1.0"))

    # MS-02 performance mode: run turn_cls and the phone detector on 1 frame in N each, staggered,
    # and reuse their last result in between (pose + tracking still run on every frame). 1 = every frame.
    # classroom.mp4 (~23 people, RTX 4060): N=1 53 ms, N=2 38-41 ms (24.6-26 FPS), N=3 35 ms (28.5 FPS);
    # DS-03 with N=3: look-at-paper 8/8, phone 12/17, false alarms 0/33 (no loss vs N=1/2).
    AUX_MODEL_EVERY_N: int = int(os.getenv("AUX_MODEL_EVERY_N", "3"))

    # FT-04 risk score: suspicious seconds inside a sliding window; RISK_FULL_S of them = 100 points
    RISK_WINDOW_S: float = float(os.getenv("RISK_WINDOW_S", "30"))
    RISK_FULL_S: float = float(os.getenv("RISK_FULL_S", "5"))
    SENSITIVITY_DEFAULT: int = int(os.getenv("SENSITIVITY_DEFAULT", "3"))   # 1 low .. 5 high, UI slider

    # FT-03 bending down to look under the desk: top of the person's box sinks >= BEND_DROP_SW shoulder
    # widths below its calibrated height for >= BEND_TRIGGER_S. DS-03: writing lowers it <= 0.14 sw.
    # Only for people big enough in frame (wide CCTV boxes jitter by more than that).
    BEND_DROP_SW: float = float(os.getenv("BEND_DROP_SW", "0.5"))
    BEND_TRIGGER_S: float = float(os.getenv("BEND_TRIGGER_S", "3.0"))
    BEND_MIN_SHOULDER_FRAC: float = 0.09

    # FT-06 evidence clips: PRE seconds before + POST seconds after each new REVIEW event
    EVIDENCE_DIR: Path = Path(os.getenv("EVIDENCE_DIR", str(BASE_DIR / "evidence")))
    EVIDENCE_PRE_S: float = float(os.getenv("EVIDENCE_PRE_S", "5.0"))
    EVIDENCE_POST_S: float = float(os.getenv("EVIDENCE_POST_S", "5.0"))
    EVIDENCE_MAX_CLIPS: int = int(os.getenv("EVIDENCE_MAX_CLIPS", "50"))   # per session, caps disk use
    BYTETRACK_CONFIG_PATH: Path = BASE_DIR / "config" / "bytetrack.yaml"
    
    
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
