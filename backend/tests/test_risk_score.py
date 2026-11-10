"""
FT-04: điểm rủi ro 0-100 theo cửa sổ trượt 30 giây + độ nhạy cảnh báo chỉnh được (1 thấp ... 5 cao).
"""
import numpy as np

from app.config import settings
from app.inference.pose_behavior import PoseBehaviorEngine
from tests.test_cheating_detection_yolo import make_kpts

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)
BOX = (0.2, 0.2, 0.8, 0.8)


def frontal():
    return make_kpts(nose_x=640, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)


def turned():
    k = make_kpts(nose_x=676, nose_y=350, l_shoulder_x=700, l_shoulder_y=400, r_shoulder_x=580, r_shoulder_y=400)
    k[3, 0], k[4, 0] = 646, 706
    k[1, 0], k[2, 0] = 656, 686
    k[3, 2] = 0.15
    return k


class Clock:
    def __init__(self):
        self.t = 1000

    def run(self, engine, track, kpts, seconds, step_ms=100):
        res = None
        for _ in range(int(seconds * 1000 / step_ms)):
            res = engine.process_student_roi(FRAME, BOX, track, 0, self.t, 0.95, kpts)
            self.t += step_ms
        return res


def calibrated(sensitivity=None):
    engine = PoseBehaviorEngine()
    if sensitivity is not None:
        engine.set_sensitivity(sensitivity)
    clock = Clock()
    clock.run(engine, 1, frontal(), 2.5)
    return engine, clock


def test_risk_score_counts_suspicious_seconds_in_last_30s():
    engine, clock = calibrated()
    res = clock.run(engine, 1, turned(), 2.0)        # 2 s of turning -> 2 / 5 s = 40 (REVIEW floor applies)
    assert res.status == "REVIEW"
    assert res.suspicion_score >= 80
    res = clock.run(engine, 1, frontal(), 5.0)       # back to normal: no longer REVIEW, score shows the history
    assert res.status != "REVIEW"
    assert 30 <= res.suspicion_score <= 50
    res = clock.run(engine, 1, frontal(), 30.0)      # the turn left the 30 s window
    assert res.suspicion_score == 0


def test_repeated_short_glances_accumulate_in_window():
    engine, clock = calibrated()
    res = None
    for _ in range(4):                               # 4 x 1.0 s glances: each too short to REVIEW alone
        res = clock.run(engine, 1, turned(), 1.0)
        res = clock.run(engine, 1, frontal(), 3.0)
    assert res.status != "REVIEW"
    assert res.suspicion_score >= 60                 # ~4 s suspicious within 30 s


def test_default_sensitivity_keeps_1_5s_turn_trigger():
    engine, clock = calibrated()
    assert clock.run(engine, 1, turned(), 1.2).status != "REVIEW"
    assert clock.run(engine, 1, turned(), 0.6).status == "REVIEW"


def test_high_sensitivity_triggers_sooner():
    engine, clock = calibrated(sensitivity=5)
    assert clock.run(engine, 1, turned(), 1.0).status == "REVIEW"


def test_low_sensitivity_needs_longer_turn():
    engine, clock = calibrated(sensitivity=1)
    assert clock.run(engine, 1, turned(), 2.0).status != "REVIEW"
    assert clock.run(engine, 1, turned(), 1.5).status == "REVIEW"


def test_sensitivity_is_clamped():
    engine = PoseBehaviorEngine()
    engine.set_sensitivity(99)
    assert engine.sensitivity == 5
    engine.set_sensitivity(-3)
    assert engine.sensitivity == 1
    assert settings.SENSITIVITY_DEFAULT == 3


# ---------- WebSocket: {"type": "config", "sensitivity": n} ----------
from fastapi.testclient import TestClient

from app.main import app
from app.sessions import session_manager


def test_ws_config_message_sets_session_sensitivity():
    client = TestClient(app)
    s = client.post("/api/sessions", json={"camera_label": "t"}).json()
    try:
        with client.websocket_connect(s["ws_url"]) as ws:
            ws.send_json({"type": "auth", "ws_ticket": s["ws_ticket"]})
            assert ws.receive_json()["type"] == "session_info"
            ws.send_json({"type": "config", "sensitivity": 5})
            ack = ws.receive_json()
            assert ack == {"type": "config_ack", "sensitivity": 5}
        assert session_manager.get_session(s["session_id"]).pipeline.pose_engine.sensitivity == 5
    finally:
        client.post(f"/api/sessions/{s['session_id']}/stop")
