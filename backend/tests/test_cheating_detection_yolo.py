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

    @pytest.mark.parametrize("l_sx,r_sx", [(580, 700), (700, 580)])
    def test_sustained_writing_never_flags_turning(self, l_sx, r_sx):
        """Head bowed over the desk for 5s (nose drops to/below shoulder line) is normal exam behaviour."""
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        norm_box = (0.2, 0.2, 0.8, 0.8)
        normal_kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=l_sx, l_shoulder_y=400, r_shoulder_x=r_sx, r_shoulder_y=400)
        for f in range(20):
            engine.process_student_roi(frame, norm_box, 4, f, 1000 + f * 100, 0.95, normal_kpts)

        for step in range(50):
            # nose sits just below the shoulder line, jittering slightly, while writing
            writing_kpts = make_kpts(nose_x=640 + (step % 3) - 1, nose_y=404 + (step % 5) * 2,
                                     l_shoulder_x=l_sx, l_shoulder_y=400, r_shoulder_x=r_sx, r_shoulder_y=400)
            res = engine.process_student_roi(frame, norm_box, 4, 20 + step, 3000 + step * 100, 0.95, writing_kpts)
            assert "TURNING" not in res.reasons, f"step {step}: yaw_delta={res.yaw_delta_deg}"
            assert res.status != "REVIEW"
            assert abs(res.yaw_delta_deg) <= 180.0

    def test_head_yaw_from_ears(self):
        kpts = make_kpts(nose_x=640)  # ears at +-30px around the nose
        assert abs(PoseBehaviorEngine._head_yaw_from_face(kpts)) < 1e-6
        kpts[0, 0] = 676  # nose 1.2 half-ear-distances off-centre
        assert 40 < PoseBehaviorEngine._head_yaw_from_face(kpts) < 45
        kpts[3, 2] = 0.1  # one ear hidden -> head turned towards it (profile)
        assert abs(PoseBehaviorEngine._head_yaw_from_face(kpts)) == PoseBehaviorEngine.PROFILE_YAW_DEG

    def test_sustained_head_rotation_triggers_review(self):
        """Head rotated ~42 deg with only a small nose shift over the shoulders (glancing at a neighbour)."""
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        norm_box = (0.2, 0.2, 0.8, 0.8)
        normal_kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        for f in range(20):
            engine.process_student_roi(frame, norm_box, 5, f, 1000 + f * 100, 0.95, normal_kpts)

        turned = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        turned[0, 0] = 676  # ears stay, nose swings towards one ear
        res = None
        for step in range(25):
            res = engine.process_student_roi(frame, norm_box, 5, 20 + step, 3000 + step * 100, 0.95, turned)
        assert res.status == "REVIEW"
        assert "TURNING" in res.reasons
        assert 35 < res.yaw_delta_deg < 50

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



class TestTurnClassifierFusion:
    """turn_prob = xác suất 'quay đầu' do model phân loại ảnh cắt (turn_cls) của nhóm trả về."""

    def _calibrated_engine(self, track_id):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        for f in range(20):
            engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), track_id, f, 1000 + f * 100, 0.95, kpts)
        return engine, frame, kpts

    def test_sustained_high_turn_prob_triggers_review(self):
        engine, frame, kpts = self._calibrated_engine(10)
        res = None
        for step in range(30):  # 3s, keypoints neutral, classifier sure the head is turned
            res = engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), 10, 20 + step, 3000 + step * 100,
                                             0.95, kpts, turn_prob=0.9)
        assert res.status == "REVIEW"
        assert "TURNING" in res.reasons
        assert res.ai_turn_prob is not None and res.ai_turn_prob > 0.7

    def test_brief_turn_prob_spike_does_not_review(self):
        engine, frame, kpts = self._calibrated_engine(11)
        for step in range(40):
            prob = 0.95 if 10 <= step < 14 else 0.05   # 0.4s spike
            res = engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), 11, 20 + step, 3000 + step * 100,
                                             0.95, kpts, turn_prob=prob)
            assert res.status != "REVIEW", f"step {step}"

    def test_low_turn_prob_keeps_normal(self):
        engine, frame, kpts = self._calibrated_engine(12)
        for step in range(30):
            res = engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), 12, 20 + step, 3000 + step * 100,
                                             0.95, kpts, turn_prob=0.2)
        assert res.status == "WITHIN_THRESHOLDS"
        assert res.reasons == []


class TestHeadTurnWithHiddenEar:
    """Khi quay hẳn đầu, tai phía xa bị che (conf thấp) - đây chính là lúc cần báo nhất (DS-03 v_c3_s1)."""

    def test_far_ear_hidden_gives_large_yaw(self):
        kpts = make_kpts(nose_x=640)
        kpts[1, 0], kpts[2, 0] = 619, 649   # eyes lag the nose when the head turns
        kpts[3, 2] = 0.15   # left ear hidden
        yaw = PoseBehaviorEngine._head_yaw_from_face(kpts)
        assert yaw is not None and abs(yaw) >= 45

    def test_both_ears_hidden_is_unknown(self):
        kpts = make_kpts(nose_x=640)
        kpts[3, 2] = 0.1
        kpts[4, 2] = 0.1
        assert PoseBehaviorEngine._head_yaw_from_face(kpts) is None

    def test_sustained_turn_with_hidden_ear_triggers_review(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        box = (0.2, 0.2, 0.8, 0.8)
        normal = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        for f in range(20):
            engine.process_student_roi(frame, box, 20, f, 1000 + f * 100, 0.95, normal)
        # nose shifts only 0.3 shoulder widths (below lateral radius) but the far ear disappears
        turned = make_kpts(nose_x=676, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        turned[3, 0], turned[4, 0] = 646, 706   # ears follow the head, so ear-midpoint offset alone is small
        turned[1, 0], turned[2, 0] = 656, 686   # nose sits off the eye midpoint (0.17 eye distances)
        turned[3, 2] = 0.15
        res = None
        for step in range(25):
            res = engine.process_student_roi(frame, box, 20, 20 + step, 3000 + step * 100, 0.95, turned)
        assert res.status == "REVIEW"
        assert "TURNING" in res.reasons

    def test_hidden_ear_ignored_when_person_is_small(self):
        """Ở camera toàn cảnh (vai ~40px / 960px) độ tin cậy tai chập chờn -> không suy ra quay đầu."""
        kpts = make_kpts(nose_x=640, l_shoulder_x=620, r_shoulder_x=660)   # vai rộng 40px
        kpts[3, 2] = 0.15
        assert PoseBehaviorEngine._head_yaw_from_face(kpts, frame_w=960) is None
        big = make_kpts(nose_x=640)                                        # vai rộng 120px
        big[1, 0], big[2, 0] = 619, 649
        big[3, 2] = 0.15
        assert PoseBehaviorEngine._head_yaw_from_face(big, frame_w=960) is not None


class TestRobustCalibration:
    """DS-03 v_c3_s2: thí sinh liếc sang ngay trong 2 giây lấy mốc -> mốc không được 'học' tư thế liếc."""

    @staticmethod
    def _frontal():
        return make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)

    @staticmethod
    def _turned():
        k = make_kpts(nose_x=676, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        k[3, 0], k[4, 0] = 646, 706
        k[1, 0], k[2, 0] = 656, 686
        k[3, 2] = 0.15                      # far ear hidden
        return k

    def test_glance_during_calibration_does_not_poison_baseline(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        box = (0.2, 0.2, 0.8, 0.8)
        t = 1000
        for f in range(20):                 # last 8 of 20 calibration samples are a glance
            kpts = self._frontal() if f < 12 else self._turned()
            engine.process_student_roi(frame, box, 30, f, t, 0.95, kpts)
            t += 100
        for f in range(10):
            engine.process_student_roi(frame, box, 30, 20 + f, t, 0.95, self._frontal())
            t += 100
        res = None
        for f in range(25):
            res = engine.process_student_roi(frame, box, 30, 30 + f, t, 0.95, self._turned())
            t += 100
        assert res.status == "REVIEW"
        assert "TURNING" in res.reasons

    def test_frontal_after_calibration_stays_normal(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        box = (0.2, 0.2, 0.8, 0.8)
        t = 1000
        for f in range(20):
            kpts = self._frontal() if f < 12 else self._turned()
            engine.process_student_roi(frame, box, 31, f, t, 0.95, kpts)
            t += 100
        for f in range(30):
            res = engine.process_student_roi(frame, box, 31, 20 + f, t, 0.95, self._frontal())
            t += 100
            assert res.status != "REVIEW", f"step {f}"

    def test_hidden_ear_with_centred_nose_is_not_a_turn(self):
        """DS-03 v_c5_s7_s8: đội mũ cúi viết, tai bị vành mũ che nhưng mũi vẫn ở giữa hai mắt."""
        kpts = make_kpts(nose_x=640)          # eyes symmetric around the nose
        kpts[3, 2] = 0.05
        assert PoseBehaviorEngine._head_yaw_from_face(kpts) is None


class TestTurnClassifierPerStudentBaseline:
    """classroom.mp4: thí sinh ngồi nghiêng so với camera -> P(turn) ~0.9 ngay cả khi làm bài bình thường."""

    def test_student_who_always_looks_turned_is_not_flagged(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        res = None
        for f in range(50):
            res = engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), 40, f, 1000 + f * 100, 0.95, kpts,
                                             turn_prob=0.9)
        assert res.status != "REVIEW"

    def test_rise_above_own_baseline_is_flagged(self):
        engine = PoseBehaviorEngine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        kpts = make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
        for f in range(25):
            engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), 41, f, 1000 + f * 100, 0.95, kpts, turn_prob=0.1)
        res = None
        for f in range(25):
            res = engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), 41, 25 + f, 3500 + f * 100, 0.95, kpts,
                                             turn_prob=0.95)
        assert res.status == "REVIEW"
        assert "TURNING" in res.reasons
