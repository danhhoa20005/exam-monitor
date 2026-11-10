"""
A2 / MS-02 performance mode: the two helper models (turn_cls, phone detector) run on alternate
frames, staggered so no frame pays for both. A skipped frame reuses the last result, so the
per-student smoothing and timers see the same signal rate as before.
"""
import numpy as np

from app.config import settings
from app.inference import tracking_core

FRAME = np.zeros((540, 960, 3), np.uint8)


def det(track_id, x1=0.1):
    return (track_id, (x1, 0.2, x1 + 0.1, 0.6), 0.9, "person", None)


class FakeTurn:
    def __init__(self):
        self.calls = 0

    def predict(self, frame, boxes):
        self.calls += 1
        return [0.1 * self.calls] * len(boxes)


class FakePhone:
    def __init__(self):
        self.calls = 0

    def __call__(self, frame, **kw):
        self.calls += 1
        box = [100.0 * self.calls, 0, 100.0 * self.calls + 20, 40]
        xyxy = type("T", (), {"tolist": lambda s: [box]})()
        return [type("R", (), {"boxes": type("B", (), {"xyxy": xyxy})()})()]


def make(monkeypatch, every_n):
    monkeypatch.setattr(tracking_core.SessionInferencePipeline, "_init_yolo", lambda self: None)
    monkeypatch.setattr(settings, "AUX_MODEL_EVERY_N", every_n)
    p = tracking_core.SessionInferencePipeline("t")
    p.turn_classifier, p.phone_detector = FakeTurn(), FakePhone()
    return p


def run(p, dets):
    return p._aux_inputs(FRAME, dets, 960, 540)


def test_every_frame_when_n_is_1(monkeypatch):
    p = make(monkeypatch, 1)
    for _ in range(4):
        run(p, [det(1)])
    assert p.turn_classifier.calls == 4 and p.phone_detector.calls == 4


def test_half_rate_and_staggered_when_n_is_2(monkeypatch):
    p = make(monkeypatch, 2)
    ran_both = False
    for _ in range(6):
        t0, f0 = p.turn_classifier.calls, p.phone_detector.calls
        run(p, [det(1)])
        ran_both |= p.turn_classifier.calls > t0 and p.phone_detector.calls > f0
    assert p.turn_classifier.calls == 3 and p.phone_detector.calls == 3
    assert not ran_both


def test_skipped_frame_reuses_last_turn_prob_per_track(monkeypatch):
    p = make(monkeypatch, 2)
    probs, _ = run(p, [det(1)])          # frame 0: classifier runs
    assert probs == [0.1]
    probs, _ = run(p, [det(1), det(2, 0.5)])   # frame 1: skipped
    assert probs == [0.1, None]           # track 1 keeps its last value, new track 2 has none yet


def test_skipped_frame_reuses_last_phone_boxes(monkeypatch):
    p = make(monkeypatch, 2)
    _, boxes0 = run(p, [det(1)])          # frame 0: phone skipped, nothing seen yet
    assert boxes0 is None
    _, boxes1 = run(p, [det(1)])          # frame 1: phone detector runs
    _, boxes2 = run(p, [det(1)])          # frame 2: skipped -> same boxes
    assert boxes1 == boxes2 == [[100.0, 0, 120.0, 40]]


def test_reset_tracking_forgets_cached_results(monkeypatch):
    p = make(monkeypatch, 2)
    run(p, [det(1)])
    run(p, [det(1)])
    p.reset_tracking(0)
    probs, boxes = run(p, [det(1)])       # counter restarts: classifier runs, phone skipped
    assert boxes is None
    assert p.turn_classifier.calls == 2


def test_no_detections_runs_nothing(monkeypatch):
    p = make(monkeypatch, 1)
    probs, boxes = run(p, [])
    assert probs == [] and boxes is None
    assert p.turn_classifier.calls == 0 and p.phone_detector.calls == 0
