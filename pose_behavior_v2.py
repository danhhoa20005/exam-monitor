"""Front-camera exam review signals with occlusion-aware feature validity.

Body calibration survives brief gaps and does not depend on PnP or wrists.
Hold timers count only observed intervals after smoothing. Body ratios use
person height; CSV includes missing-data reasons and review onset timestamps.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from types import SimpleNamespace

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from tracking_core import CSV_FIELDS, TrackingSession

# ---------------------------------------------------------------------------
# CSV schema — backward-compatible superset of v1 POSE_FIELDS
# ---------------------------------------------------------------------------
POSE_FIELDS = [
    # --- v1 fields (kept for compatibility) ---
    "pose_status", "pose_valid", "pose_sample_frame",
    "yaw", "pitch", "yaw_delta",
    "nose_y", "is_turning", "is_bending",
    "review_turning", "review_bending",
    # --- v2 additions ---
    "shoulder_tilt", "is_leaning",       # Nghiêng vai/người
    "arm_raised",                         # Giơ tay
    "head_shoulder_bend",                 # Cúi đầu theo tỉ lệ head/shoulder
    "yaw_velocity",                       # Tốc độ quay đầu (°/s)
    "turn_count_10s",                     # Số lần quay trong 10s gần nhất
    "suspicion_score",                    # Điểm nghi ngờ tổng hợp 0–100
    "suspicion_level",                    # UNKNOWN / NORMAL / ATTENTION / WARNING / ALERT
    "pose_reason", "head_pose_valid", "body_pose_valid",
    "pose_sample_timestamp_ms", "review_started_ms",
    "side_reach_ratio", "is_side_reaching", "review_side_reaching",
    "review_repeated_turning", "review_hand_proximity", "review_required",
    "review_reasons", "peer_track_ids", "hand_distance_ratio",
    "shoulder_center_x", "shoulder_center_y", "person_height",
    "left_wrist_x", "left_wrist_y", "right_wrist_x", "right_wrist_y",
    "left_reach_ratio", "right_reach_ratio",
]


# ---------------------------------------------------------------------------
# Low-level pose measurement (unchanged PnP logic + extended features)
# ---------------------------------------------------------------------------
def calculate_pose_behaviors(landmarks, frame_shape, initial_nose_y=None,
                             initial_yaw=None, yaw_threshold=25.0,
                             bend_drop_ratio=0.12, person_height=None,
                             diagnostics=None):
    """Measure visible features independently; None means no usable body evidence.

    Head angles are approximate PnP estimates, not calibrated face angles.
    Body ratios use the person's bbox height when supplied by the session.
    """
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics["reason"] = "invalid_landmarks"
    h, w = frame_shape[:2]
    scale = max(float(person_height if person_height is not None else h), 1.0)
    if landmarks is None or len(landmarks) != 33:
        return None

    def visible(i):
        p = landmarks[i]
        return (p.visibility is not None and np.isfinite(p.visibility)
                and p.visibility >= 0.5
                and (p.presence is None or
                     (np.isfinite(p.presence) and p.presence >= 0.5))
                and np.isfinite([p.x, p.y]).all()
                and 0 <= p.x <= 1 and 0 <= p.y <= 1)

    if not all(visible(i) for i in (0, 11, 12)):
        diagnostics["reason"] = "low_confidence_nose_or_shoulders"
        return None
    xy = np.array([(p.x * w, p.y * h) for p in landmarks], dtype=np.float64)
    pitch = yaw = None
    reason = "head_landmarks_occluded"
    if all(visible(i) for i in (0, 3, 6, 7, 8)):
        model_points = np.array([
            (0, 0, 0), (30, -30, 30), (-30, -30, 30),
            (70, 0, 50), (-70, 0, 50),
        ], dtype=np.float64)
        image_points = np.ascontiguousarray(xy[[0, 3, 6, 7, 8]])
        camera = np.array([[w, 0, w / 2], [0, w, h / 2], [0, 0, 1]], dtype=np.float64)
        distortion = np.zeros((4, 1), dtype=np.float64)
        reason = "pnp_failed"
        try:
            ok, rvec, tvec = cv2.solvePnP(
                model_points, image_points, camera, distortion,
                flags=cv2.SOLVEPNP_EPNP)
            if ok:
                ok, rvec, tvec = cv2.solvePnP(
                    model_points, image_points, camera, distortion,
                    rvec=rvec, tvec=tvec, useExtrinsicGuess=True,
                    flags=cv2.SOLVEPNP_ITERATIVE)
            if ok and np.isfinite(rvec).all() and np.isfinite(tvec).all():
                rotation, _ = cv2.Rodrigues(rvec)
                if np.all((rotation @ model_points.T + tvec)[2] > 0):
                    angles = cv2.RQDecomp3x3(rotation)[0]
                    if np.isfinite(angles[:2]).all():
                        pitch, yaw = float(angles[0]), float(angles[1])
                        reason = "ok"
        except cv2.error:
            pass  # Retain body measurements even when PnP fails.

    nose_y = float(xy[0, 1])
    l_sh, r_sh = xy[11], xy[12]
    shoulder_mid_y = (l_sh[1] + r_sh[1]) / 2
    yaw_delta = (None if yaw is None else yaw if initial_yaw is None
                 else (yaw - initial_yaw + 180) % 360 - 180)
    bending = (nose_y - initial_nose_y > bend_drop_ratio * scale
               if initial_nose_y is not None else shoulder_mid_y - nose_y < 0.04 * scale)
    left_arm = bool(xy[13, 1] < l_sh[1]) if visible(13) else None
    right_arm = bool(xy[14, 1] < r_sh[1]) if visible(14) else None
    arm_raised = (True if left_arm or right_arm else
                  False if left_arm is False and right_arm is False else None)
    # Image-space horizontal reach beyond the outer shoulder, at desk height.
    # A raised hand alone is not a reach. Hidden elbows/wrists remain unknown.
    shoulder_left, shoulder_right = sorted((l_sh[0], r_sh[0]))
    arms = {}
    for side, elbow, wrist in (("left", 13, 15), ("right", 14, 16)):
        usable = visible(elbow) and visible(wrist)
        point = xy[wrist] if usable else None
        ratio = None
        if usable:
            in_band = shoulder_mid_y - .05 * scale <= point[1] <= shoulder_mid_y + .60 * scale
            extension = max(shoulder_left - point[0], point[0] - shoulder_right, 0.)
            ratio = float(extension / scale) if in_band else 0.
        arms.update({f"{side}_wrist_x": None if point is None else float(point[0]),
                     f"{side}_wrist_y": None if point is None else float(point[1]),
                     f"{side}_reach_ratio": ratio})
    observed = [arms[f"{side}_reach_ratio"] for side in ("left", "right")
                if arms[f"{side}_reach_ratio"] is not None]
    diagnostics["reason"] = reason
    return dict(
        yaw=yaw, pitch=pitch, yaw_delta=yaw_delta, nose_y=nose_y,
        is_turning=None if yaw_delta is None else bool(abs(yaw_delta) > yaw_threshold),
        is_bending=bool(bending),
        shoulder_tilt=float(abs(l_sh[1] - r_sh[1]) / scale),
        arm_raised=arm_raised,
        head_shoulder_bend=float((shoulder_mid_y - nose_y) / scale),
        head_pose_valid=yaw is not None, body_pose_valid=True, pose_reason=reason,
        shoulder_center_x=float((l_sh[0] + r_sh[0]) / 2),
        shoulder_center_y=float(shoulder_mid_y), person_height=scale,
        side_reach_ratio=max(observed) if observed else None, **arms,
    )


# ---------------------------------------------------------------------------
# TemporalSmoother — suppress noisy single-frame spikes
# ---------------------------------------------------------------------------
class TemporalSmoother:
    """Majority-vote filter over a sliding window for boolean signals."""

    def __init__(self, window_size: int = 5, min_ratio: float = 0.6):
        self.window: deque = deque(maxlen=window_size)
        self.min_ratio = min_ratio

    def update(self, measurement: dict | None) -> dict | None:
        self.window.append(measurement)
        if measurement is None:
            return None
        if len(self.window) < 3:
            return measurement

        valid = [m for m in self.window if m is not None]
        if not valid:
            return measurement

        smoothed = dict(measurement)

        # Smooth boolean signals via majority vote
        for key in ("is_turning", "is_bending", "is_leaning", "arm_raised", "is_side_reaching"):
            if key in smoothed and smoothed[key] is not None:
                observed = [m[key] for m in valid if m.get(key) is not None]
                # Never extend an event using only historical true votes.
                smoothed[key] = bool(measurement[key] and
                                     sum(observed) / len(observed) >= self.min_ratio)

        return smoothed


# ---------------------------------------------------------------------------
# SuspicionScorer — weighted 0–100 composite score
# ---------------------------------------------------------------------------
class SuspicionScorer:
    """Review priority, not a probability of cheating.

    Writing/bending, shoulder lean and asking for help (raised hand) alone
    carry no points. Stronger levels require corroborating observable cues.
    """

    WEIGHTS = {
        "sustained_turn": 35,
        "turn_with_body": 15,
        "side_reach": 35,
        "hand_proximity": 60,
        "turn_frequency": 30,
    }

    # Thresholds
    LEAN_THRESHOLD = 0.04        # shoulder_tilt_ratio (4% chiều cao người)
    TURN_FREQ_THRESHOLD = 3      # >= 3 lần quay trong 10s

    LEVELS = [
        (80, "ALERT"),
        (60, "WARNING"),
        (30, "ATTENTION"),
        (0, "NORMAL"),
    ]

    def compute(self, features: dict) -> tuple[int, str]:
        """Return (score, level) from current features dict."""
        score = 0.0

        if features.get("review_turning"):
            score += self.WEIGHTS["sustained_turn"]

        if features.get("review_turning") and (features.get("review_bending")
                                                or features.get("is_leaning")):
            score += self.WEIGHTS["turn_with_body"]
        if features.get("review_side_reaching"):
            score += self.WEIGHTS["side_reach"]
        if features.get("review_hand_proximity"):
            score += self.WEIGHTS["hand_proximity"]
        if features.get("review_repeated_turning"):
            score += self.WEIGHTS["turn_frequency"]

        score = int(min(100, max(0, score)))
        level = "NORMAL"
        for threshold, lbl in self.LEVELS:
            if score >= threshold:
                level = lbl
                break

        return score, level


def apply_review_result(result):
    """Compose track and pair evidence consistently for CSV, overlay and counters."""
    reasons = [name for key, name in (
        ("review_turning", "TURN"), ("review_repeated_turning", "REPEATED_TURN"),
        ("review_side_reaching", "SIDE_REACH"),
        ("review_hand_proximity", "HAND_PROXIMITY")) if result.get(key)]
    result.update(review_required=bool(reasons), review_reasons=";".join(reasons))
    status = result.get("pose_status", "POSE_UNAVAILABLE")
    if not result.get("pose_valid") or status.startswith("WARMUP"):
        return result
    score, level = SuspicionScorer().compute(result)
    partial = result.get("yaw_delta") is None
    result.update(suspicion_score=score,
                  suspicion_level="UNKNOWN" if partial and level == "NORMAL" else level)
    if reasons:
        prefix = level if level in ("WARNING", "ALERT") else "REVIEW"
        status = prefix + "_" + "_".join(reasons)
    elif any(result.get(k) for k in ("is_turning", "is_bending", "is_leaning", "is_side_reaching")):
        status = "OBSERVING"
    else:
        status = "NORMAL"
    result["pose_status"] = ("PARTIAL_" if partial else "") + status
    if not reasons:
        result["review_started_ms"] = None
    return result


# ---------------------------------------------------------------------------
# AdaptiveBehaviorState — replaces static-calibration BehaviorState
# ---------------------------------------------------------------------------
@dataclass
class AdaptiveBehaviorState:
    """Per-track calibration and evidence timers; missing samples are unknown.

    Brief gaps preserve calibration and pause hold timers, never add evidence.
    Body and yaw calibrate independently so an occluded ear cannot block bending.
    """
    warmup_frames: int = 8
    ema_alpha: float = 0.0
    yaw_threshold: float = 25.0
    yaw_release_threshold: float = 15.0
    bend_drop_ratio: float = 0.12
    hold_seconds: float = 0.8
    reach_hold_seconds: float = 0.5
    side_reach_threshold: float = 0.18
    min_turn_seconds: float = 0.2
    turn_frequency_threshold: int = 3
    max_pose_gap_seconds: float = 2.5
    evidence_gap_seconds: float = 0.5
    samples: list = field(default_factory=list)
    yaw_samples: list = field(default_factory=list, init=False)
    baseline_nose_y: float | None = field(default=None, init=False)
    baseline_yaw: float | None = field(default=None, init=False)
    baseline_shoulder_tilt: float | None = field(default=None, init=False)
    baseline_head_shoulder_bend: float | None = field(default=None, init=False)
    last_sample_ms: float | None = field(default=None, init=False)
    last_valid_ms: float | None = field(default=None, init=False)
    last_valid_yaw_ms: float | None = field(default=None, init=False)
    last_yaw: float | None = field(default=None, init=False)
    last_yaw_ms: float | None = field(default=None, init=False)
    turn_events: list = field(default_factory=list, init=False)
    raw_turn_active: bool = field(default=False, init=False)
    turn_counted: bool = field(default=False, init=False)
    active_since: dict = field(default_factory=dict, init=False)
    evidence_ms: dict = field(default_factory=dict, init=False)
    last_flags: dict = field(default_factory=dict, init=False)
    feature_last_ms: dict = field(default_factory=dict, init=False)
    smoother: TemporalSmoother = field(default_factory=lambda: TemporalSmoother(3, 2/3), init=False)
    scorer: SuspicionScorer = field(default_factory=SuspicionScorer, init=False)

    def __post_init__(self):
        if self.warmup_frames < 1 or not 0 <= self.ema_alpha <= 1:
            raise ValueError("warmup_frames >= 1 and 0 <= ema_alpha <= 1 required")
        thresholds = (self.hold_seconds, self.max_pose_gap_seconds,
                      self.evidence_gap_seconds, self.reach_hold_seconds,
                      self.side_reach_threshold, self.min_turn_seconds, self.bend_drop_ratio)
        if not np.isfinite(thresholds).all() or min(thresholds) <= 0:
            raise ValueError("Time thresholds must be positive")
        if not 0 <= self.yaw_release_threshold < self.yaw_threshold <= 180:
            raise ValueError("Require 0 <= yaw_release_threshold < yaw_threshold <= 180")
        if self.turn_frequency_threshold < 2 or int(self.turn_frequency_threshold) != self.turn_frequency_threshold:
            raise ValueError("turn_frequency_threshold must be an integer >= 2")

    def _empty_result(self, status="POSE_UNAVAILABLE"):
        result = {key: None for key in POSE_FIELDS if key not in
                  ("pose_sample_frame", "pose_sample_timestamp_ms")}
        result.update(pose_status=status, pose_valid=False,
                      head_pose_valid=False, body_pose_valid=False,
                      review_turning=False, review_bending=False,
                      review_side_reaching=False, review_repeated_turning=False,
                      review_hand_proximity=False, review_required=False,
                      review_reasons="", peer_track_ids="",
                      pose_reason="no_measurement", suspicion_level="UNKNOWN")
        return result

    def _reset_temporal(self):
        self.active_since.clear()
        self.evidence_ms.clear()
        self.last_flags.clear()
        self.feature_last_ms.clear()
        self.smoother.window.clear()
        self.last_yaw = self.last_yaw_ms = None
        self.raw_turn_active = self.turn_counted = False

    def _hold(self, key, flag, timestamp_ms, dt_ms, hold_seconds=None):
        last = self.feature_last_ms.get(key)
        if last is not None and timestamp_ms - last > self.evidence_gap_seconds * 1000:
            self.active_since.pop(key, None)
            self.evidence_ms.pop(key, None)
            self.last_flags.pop(key, None)
        previous = self.last_flags.get(key)
        if flag is None:
            self.last_flags[key] = None
            return False, False, False
        self.feature_last_ms[key] = timestamp_ms
        onset = bool(flag and key not in self.active_since)
        rapid = bool(key == "turn" and flag is False and previous is True
                     and 0 < self.evidence_ms.get(key, 0) < 500)
        if flag:
            self.active_since.setdefault(key, timestamp_ms)
            if previous is True:
                self.evidence_ms[key] = self.evidence_ms.get(key, 0) + dt_ms
            else:
                self.evidence_ms.setdefault(key, 0)
        else:
            self.active_since.pop(key, None)
            self.evidence_ms.pop(key, None)
        self.last_flags[key] = flag
        duration = self.hold_seconds if hold_seconds is None else hold_seconds
        held = bool(flag and self.evidence_ms.get(key, 0) + 1e-6 >= duration * 1000)
        return held, onset, rapid

    def update(self, measurement, timestamp_ms, frame_height):
        if not np.isfinite(timestamp_ms) or (self.last_sample_ms is not None and timestamp_ms <= self.last_sample_ms):
            raise ValueError("Pose timestamps must increase")
        dt_ms = 0 if self.last_sample_ms is None else timestamp_ms - self.last_sample_ms
        self.last_sample_ms = timestamp_ms
        gap_ms = 0 if self.last_valid_ms is None else timestamp_ms - self.last_valid_ms
        if gap_ms > self.evidence_gap_seconds * 1000:
            self._reset_temporal()
            dt_ms = 0
        if gap_ms > self.max_pose_gap_seconds * 1000:
            if self.baseline_nose_y is None:
                self.samples.clear()
            if self.baseline_yaw is None:
                self.yaw_samples.clear()
            self.turn_events.clear()
        if measurement is None:
            self.last_flags = {key: None for key in self.last_flags}
            self.last_yaw = self.last_yaw_ms = None
            self.smoother.update(None)
            return self._empty_result()
        self.last_valid_ms = timestamp_ms
        self.turn_events = [t for t in self.turn_events if t >= timestamp_ms - 10_000]
        yaw = measurement.get("yaw")
        if (self.baseline_yaw is None and self.last_valid_yaw_ms is not None
                and timestamp_ms - self.last_valid_yaw_ms > self.max_pose_gap_seconds * 1000):
            self.yaw_samples.clear()
        if yaw is not None:
            if (self.last_valid_yaw_ms is not None and
                    timestamp_ms - self.last_valid_yaw_ms > self.evidence_gap_seconds * 1000):
                self.raw_turn_active = self.turn_counted = False
            self.last_valid_yaw_ms = timestamp_ms
        nose_y = measurement["nose_y"]
        tilt = measurement["shoulder_tilt"]
        bend_ratio = measurement["head_shoulder_bend"]
        was_body_ready = self.baseline_nose_y is not None
        was_yaw_ready = self.baseline_yaw is not None
        if not was_body_ready:
            self.samples.append((nose_y, tilt, bend_ratio))
            if len(self.samples) >= self.warmup_frames:
                baseline = np.median(self.samples, axis=0)
                (self.baseline_nose_y, self.baseline_shoulder_tilt,
                 self.baseline_head_shoulder_bend) = map(float, baseline)
        if not was_yaw_ready and yaw is not None:
            self.yaw_samples.append(yaw)
            if len(self.yaw_samples) >= self.warmup_frames:
                # Unwrap around the first sample before taking a circular median.
                anchor = self.yaw_samples[0]
                offsets = [(v - anchor + 180) % 360 - 180 for v in self.yaw_samples]
                self.baseline_yaw = float((anchor + np.median(offsets) + 180) % 360 - 180)
        result = dict(measurement, pose_valid=True, review_turning=False,
                      review_bending=False, review_started_ms=None,
                      review_side_reaching=False, review_repeated_turning=False,
                      review_hand_proximity=False, review_required=False,
                      review_reasons="", peer_track_ids="", hand_distance_ratio=None,
                      yaw_delta=None, yaw_velocity=None, is_turning=None,
                      is_bending=None, is_leaning=None, is_side_reaching=None,
                      turn_count_10s=len(self.turn_events),
                      suspicion_score=None, suspicion_level="UNKNOWN")
        if not was_body_ready:
            result["pose_status"] = f"WARMUP_{len(self.samples)}/{self.warmup_frames}"
            return result

        delta = None if yaw is None or not was_yaw_ready else (yaw - self.baseline_yaw + 180) % 360 - 180
        velocity = None
        if yaw is not None and self.last_yaw is not None and self.last_yaw_ms is not None:
            elapsed = timestamp_ms - self.last_yaw_ms
            if 0 < elapsed <= self.evidence_gap_seconds * 1000:
                velocity = abs((yaw - self.last_yaw + 180) % 360 - 180) * 1000 / elapsed
        self.last_yaw, self.last_yaw_ms = yaw, timestamp_ms if yaw is not None else None
        # Relative head-to-shoulder distance is invariant to whole-person translation.
        bending = bool(bend_ratio < self.baseline_head_shoulder_bend - self.bend_drop_ratio)
        leaning = bool(tilt > self.baseline_shoulder_tilt + self.scorer.LEAN_THRESHOLD)
        raw_turn = None
        if delta is not None:
            threshold = self.yaw_release_threshold if self.raw_turn_active else self.yaw_threshold
            raw_turn = bool(abs(delta) > threshold)
            self.raw_turn_active = raw_turn
        # Require an observed excursion, not a one-frame onset, for repetition.
        confirmed, _, _ = self._hold("turn_count", raw_turn, timestamp_ms, dt_ms, self.min_turn_seconds)
        if raw_turn is False:
            self.turn_counted = False
        if confirmed and not self.turn_counted:
            self.turn_events.append(self.active_since["turn_count"])
            self.turn_counted = True
        reaches = [measurement.get(f"{side}_reach_ratio") for side in ("left", "right")]
        reaching = (True if any(v is not None and v >= self.side_reach_threshold for v in reaches)
                    else False if all(v is not None for v in reaches) else None)
        result.update(yaw_delta=delta, yaw_velocity=velocity,
                      is_turning=raw_turn, is_bending=bending, is_leaning=leaning,
                      is_side_reaching=reaching)
        result = self.smoother.update(result) or result
        review_turn, _, _ = self._hold("turn", result["is_turning"], timestamp_ms, dt_ms)
        review_bend, _, _ = self._hold("bend", result["is_bending"], timestamp_ms, dt_ms)
        review_reach, _, _ = self._hold("reach", result["is_side_reaching"], timestamp_ms, dt_ms,
                                       self.reach_hold_seconds)
        repeated = delta is not None and len(self.turn_events) >= self.turn_frequency_threshold
        result.update(review_turning=review_turn, review_bending=review_bend,
                      review_side_reaching=review_reach, review_repeated_turning=repeated,
                      turn_count_10s=len(self.turn_events))
        starts = [self.active_since[key] for key, held in
                  (("turn", review_turn), ("reach", review_reach)) if held]
        if repeated:
            starts.append(self.turn_events[-self.turn_frequency_threshold])
        result["review_started_ms"] = min(starts) if starts else None
        # Never adapt towards a detected event or an unknown head/arm signal.
        if (delta is not None and abs(delta) <= self.yaw_release_threshold and not bending
                and not leaning and reaching is False and not repeated
                and measurement.get("arm_raised") is False):
            a = self.ema_alpha
            self.baseline_nose_y += a * (nose_y - self.baseline_nose_y)
            self.baseline_yaw = (self.baseline_yaw + a * delta + 180) % 360 - 180
            self.baseline_shoulder_tilt += a * (tilt - self.baseline_shoulder_tilt)
            self.baseline_head_shoulder_bend += a * (bend_ratio - self.baseline_head_shoulder_bend)
        result["pose_status"] = "NORMAL"
        return apply_review_result(result)


@dataclass
class HandProximityAnalyzer:
    """Two-person review cue; 2D wrist proximity does not establish object transfer.

    Only paired, fresh observations accrue time. Reusing a cached wrist never
    adds evidence. Row/scale gates are front-camera heuristics, not seat mapping.
    """
    hold_seconds: float = 0.4
    distance_ratio: float = 0.12
    reach_threshold: float = 0.18
    max_sample_age_seconds: float = 0.25
    evidence_gap_seconds: float = 0.5
    max_neighbor_distance_ratio: float = 1.5
    max_row_offset_ratio: float = 0.35
    min_scale_similarity: float = 0.65
    pairs: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        values = (self.hold_seconds, self.distance_ratio, self.reach_threshold,
                  self.max_sample_age_seconds, self.evidence_gap_seconds,
                  self.max_neighbor_distance_ratio, self.max_row_offset_ratio)
        if not np.isfinite(values).all() or min(values) <= 0:
            raise ValueError("Hand proximity thresholds must be finite and positive")
        if not 0 < self.min_scale_similarity <= 1:
            raise ValueError("min_scale_similarity must be in (0, 1]")

    def _distance(self, a, b):
        required = ("shoulder_center_x", "shoulder_center_y", "person_height")
        if any(row.get(k) is None for row in (a, b) for k in required):
            return None
        ax, ay, ah = (a[k] for k in required)
        bx, by, bh = (b[k] for k in required)
        scale = min(ah, bh)
        if (not np.isfinite([ax, ay, ah, bx, by, bh]).all() or scale <= 0
                or scale / max(ah, bh) < self.min_scale_similarity
                or abs(ay - by) > self.max_row_offset_ratio * scale
                or not .25 * scale <= abs(ax - bx) <= self.max_neighbor_distance_ratio * scale):
            return None
        distances = []
        for sa in ("left", "right"):
            for sb in ("left", "right"):
                coords = [a.get(f"{sa}_wrist_x"), a.get(f"{sa}_wrist_y"),
                          b.get(f"{sb}_wrist_x"), b.get(f"{sb}_wrist_y")]
                if any(v is None for v in coords) or not np.isfinite(coords).all():
                    continue
                x1, y1, x2, y2 = coords
                # Both hands must be between the people at approximately desk height.
                if not (min(ax, bx) <= x1 <= max(ax, bx) and min(ax, bx) <= x2 <= max(ax, bx)
                        and ay - .05 * ah <= y1 <= ay + .60 * ah
                        and by - .05 * bh <= y2 <= by + .60 * bh):
                    continue
                reaches = (a.get(f"{sa}_reach_ratio"), b.get(f"{sb}_reach_ratio"))
                if not any(v is not None and v >= self.reach_threshold for v in reaches):
                    continue
                distances.append(float(np.hypot(x1 - x2, y1 - y2) / scale))
        return min(distances) if distances else None

    def update(self, rows, timestamp_ms):
        from itertools import combinations

        current_pairs = set()
        updated_ids = set()
        partners = {row["track_id"]: [] for row in rows}
        for row in rows:
            row.update(review_hand_proximity=False, peer_track_ids="", hand_distance_ratio=None)
        for a, b in combinations(sorted(rows, key=lambda row: row["track_id"]), 2):
            key = (a["track_id"], b["track_id"])
            times = (a.get("pose_sample_timestamp_ms"), b.get("pose_sample_timestamp_ms"))
            fresh = all(row.get("pose_valid") and not row.get("pose_status", "").startswith("WARMUP")
                        and t is not None and 0 <= timestamp_ms - t <= self.max_sample_age_seconds * 1000
                        for row, t in zip((a, b), times))
            distance = self._distance(a, b) if fresh else None
            if distance is None or distance > self.distance_ratio:
                if self.pairs.pop(key, None) is not None:
                    updated_ids.update(key)
                continue
            current_pairs.add(key)
            pair = self.pairs.get(key)
            if pair is None:
                pair = dict(times=times, evidence_ms=0., started_ms=max(times))
                self.pairs[key] = pair
                updated_ids.update(key)
            elif all(t > prev for t, prev in zip(times, pair["times"])):
                intervals = [t - prev for t, prev in zip(times, pair["times"])]
                if max(intervals) > self.evidence_gap_seconds * 1000:
                    pair.update(evidence_ms=0., started_ms=max(times))
                else:
                    pair["evidence_ms"] += min(intervals)
                pair["times"] = times
                updated_ids.update(key)
            for row in (a, b):
                previous = row["hand_distance_ratio"]
                row["hand_distance_ratio"] = distance if previous is None else min(previous, distance)
            if pair["evidence_ms"] + 1e-6 >= self.hold_seconds * 1000:
                for row, peer in ((a, b), (b, a)):
                    row["review_hand_proximity"] = True
                    partners[row["track_id"]].append(str(peer["track_id"]))
                    start = row.get("review_started_ms")
                    row["review_started_ms"] = pair["started_ms"] if start is None else min(start, pair["started_ms"])
        for key in self.pairs.keys() - current_pairs:
            updated_ids.update(key)
            del self.pairs[key]
        for row in rows:
            row["peer_track_ids"] = ";".join(partners[row["track_id"]])
            apply_review_result(row)
        return updated_ids


# ---------------------------------------------------------------------------
# StudentPoseSession — drop-in replacement with front-camera exam review cues
# ---------------------------------------------------------------------------
class StudentPoseSession(TrackingSession):
    """YOLOv8 tracking + per-crop MediaPipe Pose + adaptive behavior analysis.

    Drop-in replacement for v1; csv_fields is a superset.
    """
    csv_fields = CSV_FIELDS + POSE_FIELDS

    def __init__(self, model_path, tracker_path, pose_model_path, *,
                 pose_stride=3, warmup_frames=8, hold_seconds=0.8,
                 yaw_threshold=25.0, yaw_release_threshold=15.0, bend_drop_ratio=0.12,
                 ema_alpha=0.0, pose_retry_stride=1,
                 side_reach_threshold=0.18, reach_hold_seconds=0.5,
                 min_turn_seconds=0.2, turn_frequency_threshold=3,
                 hand_hold_seconds=0.4, hand_distance_ratio=0.12,
                 interaction_max_age_seconds=0.25,
                 pose_crop_padding=0.30,
                 min_pose_detection_confidence=0.5,
                 min_pose_presence_confidence=0.5,
                 evidence_gap_seconds=0.5,
                 # v1 compat: accept but ignore calibration_frames
                 calibration_frames=None,
                 **kwargs):
        super().__init__(model_path, tracker_path, **kwargs)

        if not np.isfinite(pose_crop_padding) or not 0 <= pose_crop_padding <= 1:
            raise ValueError("pose_crop_padding must be in [0, 1]")
        self.pose_crop_padding = pose_crop_padding
        self.hand_analyzer = HandProximityAnalyzer(
            hold_seconds=hand_hold_seconds, distance_ratio=hand_distance_ratio,
            reach_threshold=side_reach_threshold,
            max_sample_age_seconds=interaction_max_age_seconds,
            evidence_gap_seconds=evidence_gap_seconds)

        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path=str(pose_model_path),
                delegate=mp_python.BaseOptions.Delegate.CPU,
            ),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=min_pose_detection_confidence,
            min_pose_presence_confidence=min_pose_presence_confidence,
        )
        self.pose = vision.PoseLandmarker.create_from_options(options)
        self.pose_stride = max(1, int(pose_stride))
        self.pose_retry_stride = min(self.pose_stride, max(1, int(pose_retry_stride)))
        self.pose_reason_counts: Counter = Counter()
        self.head_pose_updates = 0
        self.last_pose_reason = "not_attempted"
        self.behavior_options = dict(
            warmup_frames=warmup_frames,
            hold_seconds=hold_seconds,
            yaw_threshold=yaw_threshold,
            yaw_release_threshold=yaw_release_threshold,
            bend_drop_ratio=bend_drop_ratio,
            ema_alpha=ema_alpha, evidence_gap_seconds=evidence_gap_seconds,
            side_reach_threshold=side_reach_threshold, reach_hold_seconds=reach_hold_seconds,
            min_turn_seconds=min_turn_seconds, turn_frequency_threshold=turn_frequency_threshold,
        )
        self.states: dict[int, AdaptiveBehaviorState] = {}
        self.cache: dict = {}
        self.pose_attempts = 0
        self.valid_pose_updates = 0
        self.review_updates = 0
        self.alert_updates = 0
        self.status_counts: Counter = Counter()
        self.closed = False

    # ---- per-crop measurement (same crop logic as v1) ----
    def _measure(self, frame, row):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = (row[k] for k in ("x1", "y1", "x2", "y2"))
        bw, bh = x2 - x1, y2 - y1
        self.last_pose_reason = "invalid_bbox"
        if not np.isfinite([x1, y1, x2, y2]).all() or min(bw, bh) <= 0:
            return None
        # Wider horizontal context retains wrists extending beyond the student bbox.
        padding = getattr(self, "pose_crop_padding", 0.30)
        left = max(0, int(x1 - padding * bw))
        top = max(0, int(y1 - 0.12 * bh))
        right = min(w, int(x2 + padding * bw))
        bottom = min(h, int(y2 + 0.12 * bh))
        if right - left < 40 or bottom - top < 40:
            self.last_pose_reason = "crop_too_small"
            return None

        rgb = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2RGB)
        result = self.pose.detect(
            mp.Image(image_format=mp.ImageFormat.SRGB,
                     data=np.ascontiguousarray(rgb)))
        if not result.pose_landmarks:
            self.last_pose_reason = "no_pose_detected"
            return None

        local = result.pose_landmarks[0]
        if len(local) != 33:
            self.last_pose_reason = "invalid_landmarks"
            return None
        # Kiểm tra mũi + tâm vai nằm trong box gốc
        nose = (left + local[0].x * (right - left),
                top + local[0].y * (bottom - top))
        shoulder = (left + (local[11].x + local[12].x) / 2 * (right - left),
                    top + (local[11].y + local[12].y) / 2 * (bottom - top))
        if not all(x1 <= px <= x2 and y1 <= py <= y2
                   for px, py in [nose, shoulder]):
            self.last_pose_reason = "pose_outside_target_bbox"
            return None

        landmarks = [
            SimpleNamespace(
                x=(left + p.x * (right - left)) / w,
                y=(top + p.y * (bottom - top)) / h,
                visibility=p.visibility,
                presence=p.presence,
            )
            for p in local
        ]
        diagnostics = {}
        measurement = calculate_pose_behaviors(
            landmarks, frame.shape, person_height=bh, diagnostics=diagnostics)
        self.last_pose_reason = diagnostics["reason"]
        return measurement

    # ---- main process loop ----
    def process(self, frame_bgr, timestamp_ms):
        annotated, records = super().process(frame_bgr, timestamp_ms)
        frame_index = self.frame_index - 1
        fh = frame_bgr.shape[0]

        visible_ids = {row["track_id"] for row in records}
        sampled_ids = set()

        # Update invisible tracks
        for tid in self.states.keys() - visible_ids:
            self.states[tid].update(None, timestamp_ms, fh)
            self.cache.pop(tid, None)

        for row in records:
            tid = row["track_id"]
            if tid not in self.states:
                self.states[tid] = AdaptiveBehaviorState(**self.behavior_options)
            state = self.states[tid]

            cached = self.cache.get(tid)
            stride = (self.pose_retry_stride if cached is not None
                      and not cached[2].get("pose_valid") else self.pose_stride)
            if cached is None or frame_index - cached[0] >= stride:
                sampled_ids.add(tid)
                self.pose_attempts += 1
                measurement = self._measure(frame_bgr, row)
                self.valid_pose_updates += measurement is not None
                behavior = state.update(measurement, timestamp_ms, fh)
                behavior["pose_reason"] = self.last_pose_reason
                self.pose_reason_counts[self.last_pose_reason] += 1
                self.head_pose_updates += bool(behavior.get("head_pose_valid"))
                self.cache[tid] = (frame_index, timestamp_ms, behavior)

            sample_frame, sample_ms, behavior = self.cache[tid]
            if timestamp_ms - sample_ms > state.max_pose_gap_seconds * 1000:
                behavior = state.update(None, timestamp_ms, fh)
                behavior["pose_reason"] = "stale_cached_pose"
                self.cache[tid] = (sample_frame, sample_ms, behavior)

            row.update(behavior, pose_sample_frame=sample_frame,
                       pose_sample_timestamp_ms=sample_ms)

        # Compare all tracks only after their measurements are ready; row order
        # and cached samples must not bias the pair timer.
        pair_updated_ids = self.hand_analyzer.update(records, timestamp_ms)
        for row in records:
            tid = row["track_id"]
            if tid in sampled_ids | pair_updated_ids:
                self.review_updates += bool(row.get("review_required"))
                self.alert_updates += row.get("suspicion_level") in ("ALERT", "WARNING")
            if tid in sampled_ids:
                status_key = row["pose_status"]
                if status_key.startswith("WARMUP_"):
                    status_key = "WARMUP"
                self.status_counts[status_key] += 1
            # ----- Annotate -----
            score = row.get("suspicion_score", 0) or 0
            level = row.get("suspicion_level", "NORMAL")
            if level == "ALERT":
                color = (0, 0, 255)       # đỏ
            elif level == "WARNING":
                color = (0, 128, 255)     # cam
            elif level == "ATTENTION" or row.get("review_required"):
                color = (0, 220, 255)     # vàng: hành vi cần xem lại
            elif level == "UNKNOWN" or not row.get("pose_valid"):
                color = (0, 220, 255)     # vàng nhạt (chưa có pose)
            else:
                color = (40, 220, 40)     # xanh

            label = f"#{tid} {row['pose_status']}"
            if row.get("yaw_delta") is not None:
                label += f" dY={row['yaw_delta']:.0f}"
            label += " S=?" if row.get("suspicion_score") is None else f" S={score}"
            if row.get("peer_track_ids"):
                label += f" peer={row['peer_track_ids']}"

            lx = max(0, int(row["x1"]))
            ly = min(annotated.shape[0] - 5, int(row["y2"]) + 15)
            cv2.putText(annotated, label, (lx, ly),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1,
                        cv2.LINE_AA)

            # Score bar below bbox
            bar_y = min(annotated.shape[0] - 3, int(row["y2"]) + 28)
            bar_w = int((int(row["x2"]) - int(row["x1"])) * score / 100)
            if bar_w > 0:
                cv2.rectangle(
                    annotated,
                    (int(row["x1"]), bar_y - 4),
                    (int(row["x1"]) + bar_w, bar_y),
                    color, -1,
                )

        # Prune stale states
        for tid in list(self.states):
            if frame_index - self.track_stats[tid]["last_frame"] > 60:
                self.states.pop(tid)
                self.cache.pop(tid, None)

        return annotated, records

    def summary(self):
        summary = super().summary()
        summary.update(
            pose_attempts=self.pose_attempts,
            valid_pose_updates=self.valid_pose_updates,
            review_updates=self.review_updates,
            alert_updates=self.alert_updates,
            pose_status_counts=dict(self.status_counts),
            pose_reason_counts=dict(self.pose_reason_counts),
            head_pose_updates=self.head_pose_updates,
            pose_unavailable_rate=(1 - self.valid_pose_updates / self.pose_attempts
                                   if self.pose_attempts else None),
            pose_retry_stride=self.pose_retry_stride,
            pose_stride=self.pose_stride,
            behavior_parameters=self.behavior_options,
            interaction_parameters={key: value for key, value in vars(self.hand_analyzer).items()
                                    if key != "pairs"},
            version="v2.2_exam_front_camera",
            warning="Điểm ưu tiên xem lại; pose và hai tay gần nhau không xác nhận nhìn bài/đưa phao.",
        )
        return summary

    def close(self):
        if not self.closed:
            self.pose.close()
            self.closed = True
