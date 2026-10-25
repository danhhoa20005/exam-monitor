"""
Đổi nguồn (bật camera / tải video khác) phải xoá trạng thái theo dõi cũ.

Lỗi gặp trên web: tải lại v_c3_s1 khi phiên vẫn giữ track + mốc tư thế lấy lúc thí sinh
đang quay đầu -> lúc quay thì báo 0°, lúc nhìn thẳng lại báo REVIEW -60° (đảo ngược).
"""
import base64

import cv2
import numpy as np

from app.inference import tracking_core
from app.inference.pose_behavior import CandidateTrackState


class FakeTracker:
    def __init__(self):
        self.resets = 0

    def reset(self):
        self.resets += 1


def make_pipeline(monkeypatch):
    monkeypatch.setattr(tracking_core.SessionInferencePipeline, "_init_yolo", lambda self: None)
    p = tracking_core.SessionInferencePipeline("t")
    tracker = FakeTracker()
    p.yolo_model = type("M", (), {"predictor": type("P", (), {"trackers": [tracker]})()})()
    p.yolo_model.track = lambda *a, **k: []
    return p, tracker


JPEG = base64.b64encode(cv2.imencode(".jpg", np.zeros((540, 960, 3), np.uint8))[1]).decode()


def calibrated_state(track_id):
    s = CandidateTrackState(track_id)
    s.is_calibrated = True
    return s


def test_same_source_keeps_baselines(monkeypatch):
    p, tracker = make_pipeline(monkeypatch)
    p.process_frame(1, 1000, 960, 540, JPEG, source_id="video-1")
    p.pose_engine.track_states[7] = calibrated_state(7)
    p.process_frame(2, 1100, 960, 540, JPEG, source_id="video-1")
    assert 7 in p.pose_engine.track_states


def test_new_source_resets_tracker_and_baselines(monkeypatch):
    p, tracker = make_pipeline(monkeypatch)
    p.process_frame(1, 1000, 960, 540, JPEG, source_id="video-1")
    p.pose_engine.track_states[7] = calibrated_state(7)
    resets_before = tracker.resets
    p.process_frame(2, 1100, 960, 540, JPEG, source_id="video-2")
    assert 7 not in p.pose_engine.track_states
    assert tracker.resets == resets_before + 1


def test_frames_without_source_id_behave_as_before(monkeypatch):
    p, tracker = make_pipeline(monkeypatch)
    p.pose_engine.track_states[7] = calibrated_state(7)
    p.process_frame(1, 1000, 960, 540, JPEG)
    assert 7 in p.pose_engine.track_states
    assert tracker.resets == 0
