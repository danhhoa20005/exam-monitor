"""
FT-01 seat registry: a stable seat number per desk position.

ByteTrack hands out a new track ID whenever a student is briefly lost (occlusion, the invigilator
walking past). A new ID that appears where a currently empty seat is takes that seat over, so the
UI keeps showing the same seat number. Seats occupied by a visible track are never taken over, and
a box of a clearly different size (someone standing / walking past) cannot take a seated student's seat.
"""
import math
from typing import Dict, List, Optional, Tuple

Box = Tuple[float, float, float, float]   # normalised x1, y1, x2, y2


class SeatRegistry:
    MATCH_FRAC = 0.5      # box centre within half a box width of a vacated seat
    ANCHOR_ALPHA = 0.2    # slow drift so a student shifting on the chair keeps the seat
    SIZE_RATIO = 1.4      # width and height must stay within this factor of the seat's box

    def __init__(self):
        self._anchors: Dict[int, List[float]] = {}      # seat -> [cx, cy, width, height]
        self._track_seat: Dict[int, int] = {}
        self._seat_track: Dict[int, int] = {}           # seat -> latest track id sitting there

    def reset(self):
        self._anchors.clear()
        self._track_seat.clear()
        self._seat_track.clear()

    def assign(self, detections: List[Tuple[int, Box]]) -> Dict[int, Tuple[int, Optional[int]]]:
        """{track_id: (seat_id, previous track id of that seat if this track just took it over)}."""
        occupied = {self._track_seat[tid] for tid, _ in detections if tid in self._track_seat}
        out: Dict[int, Tuple[int, Optional[int]]] = {}
        for tid, box in detections:
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            w, h = max(1e-6, box[2] - box[0]), max(1e-6, box[3] - box[1])
            inherited = None
            seat = self._track_seat.get(tid)
            if seat is None:
                best, best_d = None, None
                for seat_id, (ax, ay, aw, ah) in self._anchors.items():
                    if seat_id in occupied:
                        continue
                    if max(w / aw, aw / w) > self.SIZE_RATIO or max(h / ah, ah / h) > self.SIZE_RATIO:
                        continue
                    d = math.hypot(cx - ax, cy - ay)
                    if d <= self.MATCH_FRAC * aw and (best_d is None or d < best_d):
                        best, best_d = seat_id, d
                if best is not None:
                    seat = best
                    inherited = self._seat_track.get(best)
                    self._track_seat.pop(inherited, None)
                else:
                    seat = len(self._anchors) + 1
                    self._anchors[seat] = [cx, cy, w, h]
                self._track_seat[tid] = seat
                occupied.add(seat)
            anchor = self._anchors[seat]
            anchor[0] += self.ANCHOR_ALPHA * (cx - anchor[0])
            anchor[1] += self.ANCHOR_ALPHA * (cy - anchor[1])
            anchor[2] += self.ANCHOR_ALPHA * (w - anchor[2])
            anchor[3] += self.ANCHOR_ALPHA * (h - anchor[3])
            self._seat_track[seat] = tid
            out[tid] = (seat, inherited)
        return out
