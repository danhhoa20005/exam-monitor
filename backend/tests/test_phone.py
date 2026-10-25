"""
Phát hiện dùng điện thoại: detector COCO thấy 'cell phone' sát cổ tay thí sinh, kéo dài >= PHONE_TRIGGER_S.
(DS-03 dev: điện thoại gần cổ tay >= 30% khung ở 7/9 người dùng điện thoại, 0/17 người bình thường.)
"""
import numpy as np

from app.config import settings
from app.inference.pose_behavior import PoseBehaviorEngine
from app.inference.tracking_core import phone_near_wrists


def kpts():
    k = np.zeros((17, 3), dtype=np.float32)
    k[0] = [640, 300, 0.9]
    k[3], k[4] = [610, 290, 0.9], [670, 290, 0.9]
    k[1], k[2] = [625, 285, 0.9], [655, 285, 0.9]
    k[5], k[6] = [700, 400, 0.9], [580, 400, 0.9]        # shoulders 120px apart
    k[9], k[10] = [690, 520, 0.9], [590, 520, 0.9]       # wrists
    return k


def run(engine, track_id, phone_flags, start_ms=1000):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res = None
    for i, seen in enumerate(phone_flags):
        res = engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), track_id, i, start_ms + i * 100,
                                         0.95, kpts(), phone_seen=seen)
    return res


def test_phone_near_wrist_geometry():
    k = kpts()
    assert phone_near_wrists(k, [(680, 510, 700, 540)])          # on the left wrist
    assert not phone_near_wrists(k, [(400, 100, 420, 130)])      # far away on the desk
    assert not phone_near_wrists(k, [])


def test_square_fist_sized_box_is_not_a_phone():
    """DS-03 dev: bàn tay cầm bút bị nhận nhầm có khung to & gần vuông (diện tích ~0.09 vai², tỉ lệ ~1.1)."""
    k = kpts()
    assert not phone_near_wrists(k, [(670, 500, 710, 540)])     # 40x40 px, shoulders 120 px


def test_sustained_phone_triggers_review():
    engine = PoseBehaviorEngine()
    res = run(engine, 1, [False] * 20 + [True] * 20)
    assert res.status == "REVIEW"
    assert "PHONE" in res.reasons


def test_brief_phone_glimpse_does_not_review():
    engine = PoseBehaviorEngine()
    flags = [False] * 20 + [True] * 3 + [False] * 20
    engine_res = []
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for i, seen in enumerate(flags):
        engine_res.append(engine.process_student_roi(frame, (0.2, 0.2, 0.8, 0.8), 2, i, 1000 + i * 100,
                                                     0.95, kpts(), phone_seen=seen))
    assert all(r.status != "REVIEW" for r in engine_res)


def test_phone_during_calibration_reviews_right_after():
    engine = PoseBehaviorEngine()
    res = run(engine, 3, [True] * (settings.CALIBRATION_SAMPLES + 2))
    assert res.status == "REVIEW"
    assert "PHONE" in res.reasons
