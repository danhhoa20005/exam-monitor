"""
Unit tests for YOLO11 Cheating Detection metrics and temporal warning state machine.
Based on specifications from dyingangell/Cheating-detection-YOLO.
"""
import math
import numpy as np
import pytest

from app.inference.pose_behavior import PoseBehaviorEngine, CandidateTrackState
from app.config import settings

def make_kpts(
    nose_x=640, nose_y=300,
    l_shoulder_x=580, l_shoulder_y=400,
    r_shoulder_x=700, r_shoulder_y=400,
    conf=0.9
):
    """Generate 17 COCO keypoints array (N, 3)."""
    kpts = np.zeros((17, 3), dtype=np.float32)
    kpts[0] = [nose_x, nose_y, conf]
    kpts[1] = [nose_x - 15, nose_y - 15, conf]  # l_eye
    kpts[2] = [nose_x + 15, nose_y - 15, conf]  # r_eye
    kpts[3] = [nose_x - 30, nose_y - 10, conf]  # l_ear
    kpts[4] = [nose_x + 30, nose_y - 10, conf]  # r_ear
    kpts[5] = [l_shoulder_x, l_shoulder_y, conf]
    kpts[6] = [r_shoulder_x, r_shoulder_y, conf]
    kpts[7] = [l_shoulder_x - 20, l_shoulder_y + 50, conf]
    kpts[8] = [r_shoulder_x + 20, r_shoulder_y + 50, conf]
    kpts[9] = [l_shoulder_x - 30, l_shoulder_y + 100, conf]  # l_wrist
    kpts[10] = [r_shoulder_x + 30, r_shoulder_y + 100, conf] # r_wrist
    return kpts


class TestPoseSuspicionFromKpts:
    def test_centered_nose_returns_zero_rel_x(self):
        kpts = make_kpts(nose_x=640, nose_y=300, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert ok
        assert abs(rx) < 1e-4

    def test_nose_shifted_right(self):
        kpts = make_kpts(nose_x=700, nose_y=400, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert ok
        assert abs(rx - 0.5) < 1e-3

    def test_nose_shifted_left(self):
        kpts = make_kpts(nose_x=580, nose_y=400, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert ok
        assert abs(rx - (-0.5)) < 1e-3

    def test_low_nose_confidence_returns_none(self):
        kpts = make_kpts(conf=0.9)
        kpts[0, 2] = 0.1
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert not ok
        assert rx is None

    def test_low_shoulder_confidence_returns_none(self):
        kpts = make_kpts(conf=0.9)
        kpts[5, 2] = 0.1
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert not ok

    def test_shoulders_too_close_returns_none(self):
        kpts = make_kpts(l_shoulder_x=640, r_shoulder_x=640.5)
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert not ok

    def test_empty_or_none_returns_none(self):
        assert not PoseBehaviorEngine._pose_suspicion_from_kpts(None)[3]
        assert not PoseBehaviorEngine._pose_suspicion_from_kpts(np.array([]))[3]

    def test_shoulder_width_correct(self):
        kpts = make_kpts(l_shoulder_x=580, r_shoulder_x=700)
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert ok
        assert abs(sw - 120.0) < 1e-4

    def test_rel_nose_y_upward(self):
        kpts = make_kpts(nose_y=300, l_shoulder_y=400, r_shoulder_y=400)
        rx, ry, sw, ok = PoseBehaviorEngine._pose_suspicion_from_kpts(kpts)
        assert ok
        assert ry < 0


class TestPoseSuspicionWithAngle:
    def test_returns_five_values(self):
        kpts = make_kpts()
        result = PoseBehaviorEngine._pose_suspicion_with_angle(kpts)
        assert len(result) == 5
        rx, ry, sw, angle, ok = result
        assert ok
        assert isinstance(angle, float)
        assert -math.pi <= angle <= math.pi

    def test_low_confidence_fails(self):
        kpts = make_kpts()
        kpts[6, 2] = 0.1
        _, _, _, _, ok = PoseBehaviorEngine._pose_suspicion_with_angle(kpts)
        assert not ok


class TestBboxIou:
    def test_identical_boxes_iou_one(self):
        box = (100, 100, 200, 200)
        assert abs(PoseBehaviorEngine._bbox_iou_xyxy(box, box) - 1.0) < 1e-6

    def test_no_overlap_iou_zero(self):
        a = (0, 0, 100, 100)
        b = (200, 200, 300, 300)
        assert PoseBehaviorEngine._bbox_iou_xyxy(a, b) == 0.0

    def test_half_overlap(self):
        a = (0, 0, 100, 100)
        b = (50, 0, 150, 100)
        assert abs(PoseBehaviorEngine._bbox_iou_xyxy(a, b) - 1 / 3) < 1e-4


class TestCheatingBehaviorEvaluation:
    def test_calibration_and_normal_state(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        norm_box = (0.2, 0.2, 0.8, 0.8)
        kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)

        # First 20 frames calibrate
        for f in range(20):
            res = engine.process_student_roi(
                full_frame_bgr=frame,
                bbox_xyxy_norm=norm_box,
                track_id=1,
                frame_id=f,
                captured_at_ms=1000 + f * 50,
                detection_conf=0.95,
                person_kpts=kpts
            )
            if f < 19:
                assert res.status == "CALIBRATING"
            else:
                assert res.calibration_samples >= 20

        # After calibration, same normal posture should be WITHIN_THRESHOLDS
        res_calibrated = engine.process_student_roi(
            full_frame_bgr=frame,
            bbox_xyxy_norm=norm_box,
            track_id=1,
            frame_id=25,
            captured_at_ms=2500,
            detection_conf=0.95,
            person_kpts=kpts
        )
        assert res_calibrated.status == "WITHIN_THRESHOLDS"
        assert res_calibrated.suspicion_score < 30

    def test_forward_writing_is_suppressed(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        norm_box = (0.2, 0.2, 0.8, 0.8)
        normal_kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)

        # Calibrate
        for f in range(20):
            engine.process_student_roi(frame, norm_box, 2, f, 1000 + f * 50, 0.95, normal_kpts)

        # Bending forward deeply to write (large depth deviation, minimal lateral deviation)
        writing_kpts = make_kpts(nose_x=642, nose_y=450, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)
        res = engine.process_student_roi(frame, norm_box, 2, 25, 2500, 0.95, writing_kpts)
        # Should not falsely trigger immediate REVIEW
        assert res.status != "REVIEW"
        assert res.suspicion_score < 60

    def test_sustained_lateral_turn_triggers_review(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        norm_box = (0.2, 0.2, 0.8, 0.8)
        normal_kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)

        # Calibrate
        for f in range(20):
            engine.process_student_roi(frame, norm_box, 3, f, 1000 + f * 50, 0.95, normal_kpts)

        # Severe sideways turn (lateral deviation: nose shifted right by 90px)
        cheat_kpts = make_kpts(nose_x=740, nose_y=350, l_shoulder_x=580, l_shoulder_y=400, r_shoulder_x=700, r_shoulder_y=400)

        # Sustained turn over multiple seconds
        res = None
        for step in range(30):
            res = engine.process_student_roi(
                frame, norm_box, 3, 20 + step, 2000 + step * 150, 0.95, cheat_kpts
            )

        assert res is not None
        assert res.status == "REVIEW"
        assert res.suspicion_score >= 80
        assert "TURNING" in res.reasons

    def test_camera_switch_keypoint_drop_no_attribute_error(self):
        """Simulate camera switch: calibrated track suddenly receives frame without keypoints."""
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        norm_box = (0.2, 0.1, 0.8, 0.9)

        # 1. Calibrate track using direct YOLO-Pose keypoints
        base_kpts = np.array([
            [320.0, 150.0, 0.9],
            [315.0, 145.0, 0.9], [325.0, 145.0, 0.9],
            [305.0, 148.0, 0.9], [335.0, 148.0, 0.9],
            [260.0, 220.0, 0.95],
            [380.0, 220.0, 0.95],
            [240.0, 300.0, 0.9], [400.0, 300.0, 0.9],
            [230.0, 380.0, 0.9], [410.0, 380.0, 0.9]
        ], dtype=np.float32)

        for i in range(25):
            res = engine.process_student_roi(
                frame, norm_box, 99, i, i * 100, 0.95, base_kpts
            )
        assert res.calibration_samples >= 20

        # 2. Camera switches: keypoints dropped / None
        res_after_switch = engine.process_student_roi(
            frame, norm_box, 99, 26, 2600, 0.90, None
        )
        assert res_after_switch is not None
        assert res_after_switch.track_id == 99
        # No AttributeError should have occurred!

