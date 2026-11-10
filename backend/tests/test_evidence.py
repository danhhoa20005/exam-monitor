"""
FT-06: tự động lưu clip bằng chứng 5 giây trước / sau thời điểm một thí sinh chuyển sang REVIEW.
"""
import cv2
import numpy as np

from app.inference.evidence import EvidenceRecorder


def jpeg(value):
    img = np.full((48, 64, 3), value % 255, np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()


def feed(rec, start_ms, end_ms, step=100, boxes=None):
    for t in range(start_ms, end_ms + 1, step):
        rec.add_frame(t, jpeg(t // 100), boxes or {7: (0.2, 0.2, 0.6, 0.9)})


def test_clip_has_five_seconds_before_and_after(tmp_path):
    rec = EvidenceRecorder(tmp_path, pre_s=5.0, post_s=5.0, async_write=False)
    feed(rec, 0, 9000)                             # 9 s of history, only the last 5 s are kept
    assert rec.trigger("evt-a", track_id=7, reason="TURNING", t_ms=9000)
    assert rec.status("evt-a") == "recording"
    feed(rec, 9100, 14000)                         # 5 s after the alert
    assert rec.status("evt-a") == "ready"
    cap = cv2.VideoCapture(str(rec.path_for("evt-a")))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert 95 <= n <= 105                          # 4.0 s..14.0 s at 10 fps = 101 frames
    duration = n / cap.get(cv2.CAP_PROP_FPS)
    assert 9.0 <= duration <= 11.0


def test_unknown_event_is_missing(tmp_path):
    rec = EvidenceRecorder(tmp_path, async_write=False)
    assert rec.status("evt-nope") == "missing"
    assert rec.path_for("evt-nope") is None


def test_clip_limit_per_session(tmp_path):
    rec = EvidenceRecorder(tmp_path, max_clips=1, async_write=False)
    feed(rec, 0, 1000)
    assert rec.trigger("evt-1", 7, "TURNING", 1000)
    assert not rec.trigger("evt-2", 8, "PHONE", 1000)       # another student, limit reached


def test_events_of_same_track_at_same_moment_share_one_clip(tmp_path):
    rec = EvidenceRecorder(tmp_path, async_write=False)
    feed(rec, 0, 1000)
    rec.trigger("evt-turn", 7, "TURNING", 1000)
    rec.trigger("evt-phone", 7, "PHONE", 1000)
    feed(rec, 1100, 6000)
    assert rec.status("evt-turn") == rec.status("evt-phone") == "ready"
    assert rec.path_for("evt-turn") == rec.path_for("evt-phone")


def test_flush_finishes_pending_clips_early(tmp_path):
    """Đổi video / dừng phiên: không chờ đủ 5 giây sau, ghi luôn phần đã có."""
    rec = EvidenceRecorder(tmp_path, async_write=False)
    feed(rec, 0, 3000)
    rec.trigger("evt-x", 7, "TURNING", 3000)
    feed(rec, 3100, 4000)
    rec.flush()
    assert rec.status("evt-x") == "ready"


# ---------- API: /api/sessions/{id}/evidence/{event_id} ----------
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_evidence_api_serves_saved_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EVIDENCE_DIR", tmp_path)
    rec = EvidenceRecorder(tmp_path / "session-abc", async_write=False)
    feed(rec, 0, 1000)
    rec.trigger("evt-123", 7, "TURNING", 1000)
    rec.flush()

    status = client.get("/api/sessions/session-abc/evidence/evt-123/status").json()
    assert status["status"] == "ready"
    res = client.get("/api/sessions/session-abc/evidence/evt-123")
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    assert len(res.content) > 0


def test_evidence_api_unknown_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EVIDENCE_DIR", tmp_path)
    assert client.get("/api/sessions/session-abc/evidence/evt-none/status").json()["status"] == "missing"
    assert client.get("/api/sessions/session-abc/evidence/evt-none").status_code == 404


def test_evidence_api_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EVIDENCE_DIR", tmp_path)
    assert client.get("/api/sessions/session-abc/evidence/..%2F..%2Fsecret").status_code in (400, 404)
    assert client.get("/api/sessions/..%2Fx/evidence/evt-1").status_code in (400, 404)
