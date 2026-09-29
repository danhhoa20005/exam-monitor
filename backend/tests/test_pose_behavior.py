"""
Unit tests for Pose Behavioral State Machine and Specification Rules.
"""
import numpy as np
from app.inference.pose_behavior import PoseBehaviorEngine

def test_calibration_and_rules():
    engine = PoseBehaviorEngine()
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bbox_norm = (0.2, 0.1, 0.8, 0.9)
    track_id = 101

    # 1. Feed 19 samples -> should be CALIBRATING
    for f in range(1, 20):
        t_ms = f * 200
        res = engine.process_student_roi(
            full_frame_bgr=fake_frame,
            bbox_xyxy_norm=bbox_norm,
            track_id=track_id,
            frame_id=f,
            captured_at_ms=t_ms,
            detection_conf=0.9
        )
        assert res.status == "CALIBRATING"
        assert res.calibration_samples == f

    # 2. 20th sample -> calibration completes!
    res_20 = engine.process_student_roi(
        full_frame_bgr=fake_frame,
        bbox_xyxy_norm=bbox_norm,
        track_id=track_id,
        frame_id=20,
        captured_at_ms=4000,
        detection_conf=0.9
    )
    assert res_20.calibration_samples == 20
    assert res_20.status in ("WITHIN_THRESHOLDS", "CALIBRATING")

def test_gap_reset_timeout():
    engine = PoseBehaviorEngine()
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bbox_norm = (0.2, 0.1, 0.8, 0.9)
    track_id = 102

    # Calibrate with 20 samples
    for f in range(1, 21):
        engine.process_student_roi(
            fake_frame, bbox_norm, track_id, f, f * 100, 0.9
        )

    state = engine.get_or_create_state(track_id)
    assert state.is_calibrated is True

    # Simulate behavior start
    state.turning_start_time_ms = 3000
    state.turning_duration_ms = 1000
    state.last_valid_time_ms = 4000

    # Next sample arrives after 7000ms (gap = 3000ms > 2.5s)
    engine.process_student_roi(
        fake_frame, bbox_norm, track_id, 25, 7000, 0.9
    )

    # Behavior timer must have been reset due to gap > 2.5s
    assert state.turning_duration_ms == 0 or state.turning_start_time_ms == 7000
