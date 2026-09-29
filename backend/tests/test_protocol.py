"""
Unit tests for protocol schemas.
"""
from app.protocol import TrackResult, FrameResult, SuspiciousEvent, ClientFrameMessage

def test_track_result_schema():
    track = TrackResult(
        track_id=1,
        bbox_xyxy_norm=(0.1, 0.2, 0.5, 0.8),
        detection_confidence=0.95,
        pose_valid=True,
        pose_sample_frame=10,
        calibration_samples=20,
        status="WITHIN_THRESHOLDS",
        reasons=[],
        yaw_delta_deg=5.2,
        nose_drop_ratio=0.02,
        turning_duration_ms=0,
        bending_duration_ms=0,
        progress_percent=0.0
    )
    assert track.track_id == 1
    assert track.status == "WITHIN_THRESHOLDS"
    json_str = track.model_dump_json()
    assert "WITHIN_THRESHOLDS" in json_str

def test_frame_result_serialization():
    frame = FrameResult(
        session_id="test-session",
        frame_id=42,
        captured_at_ms=10000,
        processing_ms=35,
        frame_size=(640, 480),
        tracks=[],
        new_event_ids=["evt-123"]
    )
    data = frame.model_dump()
    assert data["type"] == "result"
    assert data["session_id"] == "test-session"
    assert data["new_event_ids"] == ["evt-123"]
