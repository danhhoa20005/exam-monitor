"""
Event Management and Aggregation for suspicious exam postures.
Prevents duplicate event spamming, tracks peak telemetry, and manages supervisor decisions.
"""
import uuid
import io
import csv
import json
from typing import Dict, List, Optional
from app.protocol import SuspiciousEvent, TrackResult, ReviewDecision

class EventManager:
    """Manages lifecycle of suspicious events for a single exam session."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: Dict[str, SuspiciousEvent] = {}
        # Mapping of (track_id, reason) -> active open event_id
        self.active_event_keys: Dict[tuple[int, str], str] = {}

    def process_track_alerts(
        self,
        tracks: List[TrackResult],
        captured_at_ms: int
    ) -> List[str]:
        """
        Evaluate tracks for REVIEW transitions, update active events, and close resolved ones.
        Returns list of newly created event_ids.
        """
        new_event_ids: List[str] = []
        current_active_keys: set[tuple[int, str]] = set()

        for t in tracks:
            if t.status == "REVIEW":
                reasons = t.reasons if t.reasons else ["TURNING"]
                for r in reasons:
                    key = (t.track_id, r)
                    current_active_keys.add(key)

                    if key in self.active_event_keys:
                        # Event already open: update max metrics and ongoing duration
                        eid = self.active_event_keys[key]
                        event = self.events[eid]
                        event.max_abs_yaw_delta = max(event.max_abs_yaw_delta, abs(t.yaw_delta_deg))
                        event.max_nose_drop_ratio = max(event.max_nose_drop_ratio, t.nose_drop_ratio)
                    else:
                        # Open a NEW event (transition into REVIEW)
                        eid = f"evt-{uuid.uuid4().hex[:10]}"
                        new_event = SuspiciousEvent(
                            event_id=eid,
                            session_id=self.session_id,
                            track_id=t.track_id,
                            reasons=[r],
                            start_ms=captured_at_ms - max(t.turning_duration_ms, t.bending_duration_ms),
                            confirmed_at_ms=captured_at_ms,
                            max_abs_yaw_delta=abs(t.yaw_delta_deg),
                            max_nose_drop_ratio=t.nose_drop_ratio,
                            algorithm_version="1.0.0",
                            review_decision="PENDING"
                        )
                        self.events[eid] = new_event
                        self.active_event_keys[key] = eid
                        new_event_ids.append(eid)

        # Close events whose behaviors are no longer in REVIEW
        for key, eid in list(self.active_event_keys.items()):
            if key not in current_active_keys:
                event = self.events[eid]
                event.end_ms = captured_at_ms
                event.end_reason = "RESOLVED_NORMAL"
                self.active_event_keys.pop(key, None)

        return new_event_ids

    def close_all_on_stop(self, end_time_ms: int):
        """Close all remaining open events when session stops."""
        for eid in self.active_event_keys.values():
            event = self.events[eid]
            if not event.end_ms:
                event.end_ms = end_time_ms
                event.end_reason = "SESSION_STOPPED"
        self.active_event_keys.clear()

    def update_decision(
        self,
        event_id: str,
        decision: ReviewDecision,
        reviewer_name: str = "Giám thị",
        notes: Optional[str] = None
    ) -> Optional[SuspiciousEvent]:
        """Record supervisor review decision."""
        if event_id not in self.events:
            return None
        event = self.events[event_id]
        event.review_decision = decision
        event.reviewer = reviewer_name
        event.notes = notes
        return event

    def get_all_events(self) -> List[SuspiciousEvent]:
        return list(self.events.values())

    def export_events_csv(self) -> str:
        """Export RFC-compliant CSV with UTF-8 BOM for Microsoft Excel."""
        output = io.StringIO()
        output.write("\uFEFF")  # UTF-8 BOM
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        headers = [
            "Event ID",
            "Session ID",
            "Track ID",
            "Lý do nghi vấn",
            "Bắt đầu (ms)",
            "Xác nhận (ms)",
            "Kết thúc (ms)",
            "Lý do kết thúc",
            "Max Yaw Delta (°)",
            "Max Nose Drop (%)",
            "Phiên bản thuật toán",
            "Quyết định giám thị",
            "Người duyệt",
            "Thời gian duyệt",
            "Ghi chú"
        ]
        writer.writerow(headers)

        for e in self.events.values():
            writer.writerow([
                e.event_id,
                e.session_id,
                e.track_id,
                "; ".join(e.reasons),
                e.start_ms,
                e.confirmed_at_ms,
                e.end_ms or "",
                e.end_reason or "ONGOING",
                round(e.max_abs_yaw_delta, 1),
                f"{round(e.max_nose_drop_ratio * 100, 1)}%",
                e.algorithm_version,
                e.review_decision,
                e.reviewer or "",
                e.reviewed_at or "",
                e.notes or ""
            ])

        return output.getvalue()

    def export_summary_json(self, tracks: Optional[List[TrackResult]] = None) -> dict:
        """Export comprehensive JSON summary report."""
        events_list = [e.model_dump() for e in self.events.values()]
        pending = sum(1 for e in self.events.values() if e.review_decision in ("PENDING", "NEEDS_REVIEW"))
        confirmed = sum(1 for e in self.events.values() if e.review_decision == "CONFIRMED_VIOLATION")
        dismissed = sum(1 for e in self.events.values() if e.review_decision == "DISMISSED")

        return {
            "session_id": self.session_id,
            "algorithm_version": "1.0.0",
            "metrics": {
                "total_events": len(self.events),
                "pending_reviews": pending,
                "confirmed_violations": confirmed,
                "dismissed_events": dismissed,
                "tracked_objects": len(tracks) if tracks else 0
            },
            "events": events_list,
            "tracks": [t.model_dump() for t in tracks] if tracks else []
        }
