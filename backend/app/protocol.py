"""
Pydantic data schemas for REST API and WebSocket protocol.
"""
from typing import List, Optional, Literal, Tuple
from pydantic import BaseModel, Field

# Domain Enums
TrackStatus = Literal[
    "CALIBRATING",
    "WITHIN_THRESHOLDS",
    "OBSERVING",
    "REVIEW",
    "POSE_UNAVAILABLE"
]

BehaviorReason = Literal["TURNING", "BENDING"]

ReviewDecision = Literal[
    "PENDING",
    "NEEDS_REVIEW",
    "CONFIRMED_VIOLATION",
    "DISMISSED"
]

# Client to Server Messages
class AuthMessage(BaseModel):
    type: Literal["auth"] = "auth"
    ws_ticket: str

class ClientFrameMessage(BaseModel):
    type: Literal["frame"] = "frame"
    frame_id: int
    captured_at_ms: int
    width: int
    height: int
    jpeg_base64: str

# Server to Client Messages
class TrackResult(BaseModel):
    track_id: int
    bbox_xyxy_norm: Tuple[float, float, float, float]
    detection_confidence: float
    pose_valid: bool
    pose_sample_frame: int
    calibration_samples: int
    status: TrackStatus
    reasons: List[BehaviorReason]
    yaw_delta_deg: float
    nose_drop_ratio: float
    turning_duration_ms: int
    bending_duration_ms: int
    progress_percent: Optional[float] = 0.0
    activity: Optional[str] = "attentive"
    suspicion_score: Optional[int] = 0
    suspicion_level: Optional[str] = "NORMAL"
    shoulder_tilt: Optional[float] = 0.0
    is_leaning: Optional[bool] = False
    turn_count_10s: Optional[int] = 0

class FrameResult(BaseModel):
    type: Literal["result"] = "result"
    session_id: str
    frame_id: int
    captured_at_ms: int
    processing_ms: int
    yolo_ms: Optional[int] = 0
    pose_ms: Optional[int] = 0
    frame_size: Tuple[int, int]
    tracks: List[TrackResult]
    new_event_ids: List[str] = []

class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str

# Suspicious Event Schema
class SuspiciousEvent(BaseModel):
    event_id: str
    session_id: str
    track_id: int
    reasons: List[BehaviorReason]
    start_ms: int
    confirmed_at_ms: int
    end_ms: Optional[int] = None
    end_reason: Optional[Literal["RESOLVED_NORMAL", "TRACK_LOST", "POSE_LOST", "SESSION_STOPPED"]] = None
    max_abs_yaw_delta: float
    max_nose_drop_ratio: float
    algorithm_version: str = "1.0.0"
    review_decision: ReviewDecision = "PENDING"
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None
    notes: Optional[str] = None

# REST API Request/Response Schemas
class LoginRequest(BaseModel):
    access_code: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

class LoginResponse(BaseModel):
    token: str
    expires_in: int = 86400
    supervisor_name: str = "Giám thị"

class SessionCreateRequest(BaseModel):
    camera_label: Optional[str] = "Webcam 01"
    resolution: Optional[Tuple[int, int]] = (640, 480)

class SessionCreateResponse(BaseModel):
    session_id: str
    ws_ticket: str
    created_at_ms: int
    ws_url: str

class SessionStopResponse(BaseModel):
    status: str
    session_id: str
    closed_at_ms: int
    total_events: int

class UpdateDecisionRequest(BaseModel):
    review_decision: ReviewDecision
    reviewer_name: Optional[str] = "Giám thị"
    notes: Optional[str] = None

class ReadyResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    status: str
    model_loaded: bool
    pose_loaded: bool
    model_sha256: Optional[str] = None
    version: str = "1.0.0"
    weights_path: str
