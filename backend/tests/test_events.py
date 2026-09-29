"""
Unit tests for Event Manager, deduplication and export functions.
"""
from app.inference.events import EventManager
from app.protocol import TrackResult

def test_event_deduplication():
    em = EventManager("session-test-01")

    # Track enters REVIEW
    track_review = TrackResult(
        track_id=7,
        bbox_xyxy_norm=(0.2, 0.1, 0.6, 0.9),
        detection_confidence=0.91,
        pose_valid=True,
        pose_sample_frame=42,
        calibration_samples=20,
        status="REVIEW",
        reasons=["TURNING"],
        yaw_delta_deg=41.8,
        nose_drop_ratio=0.03,
        turning_duration_ms=1600,
        bending_duration_ms=0
    )

    # Frame 1: creates exactly 1 event
    new_eids = em.process_track_alerts([track_review], captured_at_ms=8200)
    assert len(new_eids) == 1
    eid = new_eids[0]
    assert len(em.events) == 1

    # Frame 2: same track still in REVIEW -> must NOT create duplicate event
    new_eids_2 = em.process_track_alerts([track_review], captured_at_ms=8400)
    assert len(new_eids_2) == 0
    assert len(em.events) == 1

    # Supervisor updates decision
    updated = em.update_decision(eid, "CONFIRMED_VIOLATION", reviewer_name="Giám thị A")
    assert updated is not None
    assert updated.review_decision == "CONFIRMED_VIOLATION"

    # Export CSV check
    csv_str = em.export_events_csv()
    assert "CONFIRMED_VIOLATION" in csv_str
    assert "TURNING" in csv_str
