"""
FT-03: cúi gập người nhìn lén dưới bàn.

Đỉnh đầu (mép trên khung người) hạ >= BEND_DROP_SW lần độ rộng vai so với mốc, kéo dài >= BEND_TRIGGER_S
-> REVIEW lý do UNDER_DESK. Vẫn đánh giá được khi mặt bị che (cúi xuống gầm bàn thường không thấy mũi).
DS-03 dev: người viết bài bình thường đầu hạ tối đa 0.14 vai, nên ngưỡng 0.5 không đụng tới viết bài.
"""
import numpy as np

from tests.test_cheating_detection_yolo import make_kpts
from app.inference.pose_behavior import PoseBehaviorEngine

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)   # shoulders 120 px = 19% of width -> large enough


def kpts(shift_y=0.0, face_visible=True, shoulder_w=120):
    k = make_kpts(nose_x=640, nose_y=350 + shift_y, l_shoulder_x=640 + shoulder_w / 2, l_shoulder_y=400 + shift_y * 0.3,
                  r_shoulder_x=640 - shoulder_w / 2, r_shoulder_y=400 + shift_y * 0.3)
    if not face_visible:
        k[0:5, 2] = 0.05
    return k


def run(engine, track, seconds, top_y, k, t0, step_ms=100):
    res = None
    t = t0
    for _ in range(int(seconds * 1000 / step_ms)):
        res = engine.process_student_roi(FRAME, (0.3, top_y, 0.7, 0.95), track, 0, t, 0.95, k)
        t += step_ms
    return res, t


def calibrated(track=1):
    engine = PoseBehaviorEngine()
    _, t = run(engine, track, 2.5, 0.20, kpts(), 1000)
    return engine, t


def test_deep_bend_with_hidden_face_for_3s_triggers_under_desk():
    engine, t = calibrated()
    deep_top = 0.20 + 0.8 * 120 / 480          # top of the box drops by 0.8 shoulder widths
    res, _ = run(engine, 1, 3.5, deep_top, kpts(shift_y=100, face_visible=False), t)
    assert res.status == "REVIEW"
    assert "UNDER_DESK" in res.reasons


def test_short_deep_bend_does_not_review():
    engine, t = calibrated()
    deep_top = 0.20 + 0.8 * 120 / 480
    res, _ = run(engine, 1, 2.0, deep_top, kpts(shift_y=100, face_visible=False), t)
    assert res.status != "REVIEW"


def test_writing_posture_is_not_under_desk():
    engine, t = calibrated()
    writing_top = 0.20 + 0.2 * 120 / 480        # leaning over the paper: ~0.2 shoulder widths
    res, _ = run(engine, 1, 10.0, writing_top, kpts(shift_y=20), t)
    assert "UNDER_DESK" not in res.reasons
    assert res.status != "REVIEW"


def test_small_people_on_wide_cctv_are_not_judged():
    """Camera toàn cảnh: vai ~40 px/960 px, khung người chập chờn -> không áp dụng luật cúi gập."""
    engine = PoseBehaviorEngine()
    wide = np.zeros((540, 960, 3), dtype=np.uint8)
    t = 1000
    for _ in range(25):
        engine.process_student_roi(wide, (0.3, 0.20, 0.34, 0.30), 9, 0, t, 0.95, kpts(shoulder_w=40)); t += 100
    res = None
    for _ in range(40):
        res = engine.process_student_roi(wide, (0.3, 0.26, 0.34, 0.33), 9, 0, t, 0.95,
                                         kpts(shift_y=60, face_visible=False, shoulder_w=40)); t += 100
    assert res.status != "REVIEW"
