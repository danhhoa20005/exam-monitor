"""
Pose Estimation and Behavioral State Machine based on YOLO11-Pose
(Architecture & Math from dyingangell/Cheating-detection-YOLO).

Features:
- Normalized nose position relative to shoulder midpoint and shoulder width
- Signed angle deviation between nose and torso vector
- Individual student baseline auto-calibration via Exponential Moving Average (EMA)
- Separation of lateral (cheating) vs depth (writing/paper) deviation
- Forward-leaning posture suppression to prevent false positives while writing
- Camera foreshortening compensation for angled/overhead cameras
- Temporal warning score accumulation (Hazard Meter 0-100) with gentle decay
- Walking and seat-leaving detection
- Skeletal signals (shoulder tilt, arm raised, hand reach)
"""
import os
import math
import time
import statistics
try:
    import numpy as np
    import cv2
except ImportError:
    np = None
    cv2 = None
from typing import Dict, List, Optional, Tuple, Any

from app.config import settings
from app.protocol import TrackStatus, BehaviorReason, TrackResult
from app.inference.pnp_head_pose import estimate_head_pose_pnp, compute_delta_yaw
from app.inference.pose_behavior_v2 import SuspicionScorer, TemporalSmoother

class CandidateTrackState:
    """Per-track posture history, baseline calibration, and temporal warning accumulation."""
    def __init__(self, track_id: int):
        self.track_id = track_id
        
        # Baseline calibration (dyingangell/Cheating-detection-YOLO)
        self.is_calibrated: bool = False
        self.calibration_samples: int = 0
        self.base_nose_x: Optional[float] = None
        self.base_nose_y: Optional[float] = None
        self.baseline_nose_y: Optional[float] = None
        self.baseline_yaw: float = 0.0
        self.calibration_yaws: List[float] = []
        self.calibration_nose_ys: List[float] = []

        # Temporal warning accumulator (seconds)
        self.score_s: float = 0.0
        self.last_ts: float = 0.0
        self.is_away: bool = False

        # Walking detection (bbox center displacement)
        self.last_box_cx: Optional[float] = None
        self.last_box_cy: Optional[float] = None

        # Behavior timers (in milliseconds)
        self.last_valid_time_ms: Optional[int] = None
        self.turning_start_time_ms: Optional[int] = None
        self.turning_duration_ms: int = 0
        self.bending_start_time_ms: Optional[int] = None
        self.bending_duration_ms: int = 0
        
        # Behavioral features
        self.turn_events: List[int] = []
        self.was_turning: bool = False
        self.shoulder_tilt: float = 0.0
        self.is_leaning: bool = False
        self.scorer = SuspicionScorer()
        self.smoother = TemporalSmoother(window_size=3, min_ratio=0.6)
        
        # Recent telemetry
        self.last_yaw: float = 0.0
        self.last_nose_drop_ratio: float = 0.0
        self.last_status: TrackStatus = "CALIBRATING"
        self.suspicion_score: int = 0
        self.suspicion_level: str = "NORMAL"

    def reset_calibration(self):
        """Reset ongoing calibration samples if track was interrupted."""
        self.calibration_yaws.clear()
        self.calibration_nose_ys.clear()
        self.base_nose_x = None
        self.base_nose_y = None
        self.baseline_nose_y = None
        self.baseline_yaw = 0.0
        self.calibration_samples = 0
        self.is_calibrated = False

    def reset_behavior_timers(self):
        """Reset continuous behavior accumulation."""
        self.turning_start_time_ms = None
        self.turning_duration_ms = 0
        self.bending_start_time_ms = None
        self.bending_duration_ms = 0
        self.was_turning = False


class PoseBehaviorEngine:
    """Engine managing YOLO11-Pose keypoints and per-track cheating behavior evaluation."""
    def __init__(self):
        self.track_states: Dict[int, CandidateTrackState] = {}
        print("[OK] YOLO11-Pose Cheating Detection Engine initialized (dyingangell/Cheating-detection-YOLO).")

    def reset_session(self):
        """Clear all tracking states when session stops."""
        self.track_states.clear()

    def get_or_create_state(self, track_id: int) -> CandidateTrackState:
        if track_id not in self.track_states:
            self.track_states[track_id] = CandidateTrackState(track_id)
        return self.track_states[track_id]

    def remove_lost_tracks(self, active_track_ids: List[int]):
        """Remove tracks that are no longer active in the frame."""
        for tid in list(self.track_states.keys()):
            if tid not in active_track_ids:
                if not self.track_states[tid].is_calibrated:
                    self.track_states.pop(tid, None)

    # -------------------------------------------------------------------------
    # Core Mathematical Functions (from dyingangell/Cheating-detection-YOLO)
    # -------------------------------------------------------------------------

    @staticmethod
    def _pose_suspicion_from_kpts(person_kpts: Any, conf_min: float = 0.3):
        """
        Extract nose position relative to shoulder midpoint, normalized by shoulder width.
        COCO keypoints:
          0: nose, 5: left_shoulder, 6: right_shoulder
        Returns: (rel_nose_x, rel_nose_y, shoulder_w, confidence_ok)
        """
        if person_kpts is None:
            return None, None, None, False
        if isinstance(person_kpts, np.ndarray) and person_kpts.size == 0:
            return None, None, None, False
        if len(person_kpts) < 7:
            return None, None, None, False

        def kp(i):
            pt = person_kpts[i]
            x, y = float(pt[0]), float(pt[1])
            c = float(pt[2]) if len(pt) > 2 else 1.0
            return x, y, c

        nx, ny, nc = kp(0)
        lsx, lsy, lsc = kp(5)
        rsx, rsy, rsc = kp(6)

        if nc < conf_min or lsc < conf_min or rsc < conf_min:
            return None, None, None, False

        shoulder_w = abs(rsx - lsx)
        if shoulder_w < 1.0:
            return None, None, None, False

        mid_x = (lsx + rsx) / 2.0
        mid_y = (lsy + rsy) / 2.0

        rel_nose_x = (nx - mid_x) / shoulder_w
        rel_nose_y = (ny - mid_y) / shoulder_w

        return rel_nose_x, rel_nose_y, shoulder_w, True

    @staticmethod
    def _pose_suspicion_with_angle(person_kpts: Any, conf_min: float = 0.3):
        """
        Extended pose suspicion: also computes nose-vs-torso signed angle (radians).
        Returns: (rel_nose_x, rel_nose_y, shoulder_w, angle_diff, confidence_ok)
        angle_diff is in (-pi, pi]
        """
        if person_kpts is None:
            return None, None, None, None, False
        if isinstance(person_kpts, np.ndarray) and person_kpts.size == 0:
            return None, None, None, None, False
        if len(person_kpts) < 7:
            return None, None, None, None, False

        def kp(i):
            pt = person_kpts[i]
            x, y = float(pt[0]), float(pt[1])
            c = float(pt[2]) if len(pt) > 2 else 1.0
            return x, y, c

        nx, ny, nc = kp(0)
        lsx, lsy, lsc = kp(5)
        rsx, rsy, rsc = kp(6)

        if nc < conf_min or lsc < conf_min or rsc < conf_min:
            return None, None, None, None, False

        shoulder_w = abs(rsx - lsx)
        if shoulder_w < 1.0:
            return None, None, None, None, False

        mid_x = (lsx + rsx) / 2.0
        mid_y = (lsy + rsy) / 2.0

        rel_nose_x = (nx - mid_x) / shoulder_w
        rel_nose_y = (ny - mid_y) / shoulder_w

        # Torso vector (right - left)
        tx = rsx - lsx
        ty = rsy - lsy
        # Normal vector pointing forward
        fx = -ty
        fy = tx

        try:
            angle_nose = math.atan2(ny - mid_y, nx - mid_x)
            angle_torso = math.atan2(fy, fx)
            angle_diff = (angle_nose - angle_torso + math.pi) % (2 * math.pi) - math.pi
        except Exception:
            angle_diff = 0.0

        return rel_nose_x, rel_nose_y, shoulder_w, float(angle_diff), True

    @staticmethod
    def _bbox_iou_xyxy(a_xyxy, b_xyxy) -> float:
        """Calculate intersection over union of two xyxy bounding boxes."""
        try:
            ax1, ay1, ax2, ay2 = map(float, a_xyxy[:4])
            bx1, by1, bx2, by2 = map(float, b_xyxy[:4])
        except Exception:
            return 0.0

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0.0:
            return 0.0

        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - inter
        if union <= 0.0:
            return 0.0

        return inter / union

    # -------------------------------------------------------------------------
    # Frame & Candidate Evaluation Pipeline
    # -------------------------------------------------------------------------

    def process_student_roi(
        self,
        full_frame_bgr: Any,
        bbox_xyxy_norm: Tuple[float, float, float, float],
        track_id: int,
        frame_id: int,
        captured_at_ms: int,
        detection_conf: float,
        person_kpts: Optional[Any] = None,
        activity: str = "attentive"
    ) -> TrackResult:
        """
        Process single tracked candidate using YOLO11-Pose keypoints and Cheating-detection-YOLO algorithm.
        """
        h_frame, w_frame = full_frame_bgr.shape[:2]
        x1_n, y1_n, x2_n, y2_n = bbox_xyxy_norm
        
        state = self.get_or_create_state(track_id)
        now_ts = captured_at_ms / 1000.0
        dt = max(0.0, min(0.25, float(now_ts - state.last_ts))) if state.last_ts > 0 else 0.05
        state.last_ts = now_ts

        # 1. Walking detection from bbox center displacement
        box_cx = (x1_n + x2_n) * 0.5 * w_frame
        box_cy = (y1_n + y2_n) * 0.5 * h_frame
        is_walking = False
        if state.last_box_cx is not None and state.last_box_cy is not None:
            move_dist = math.hypot(box_cx - state.last_box_cx, box_cy - state.last_box_cy)
            if move_dist > settings.POSE_WALK_PX:
                is_walking = True
        state.last_box_cx = box_cx
        state.last_box_cy = box_cy

        # 2. Extract pose keypoints
        has_direct_kpts = person_kpts is not None and len(person_kpts) >= 7
        rel_nose_x, rel_nose_y, shoulder_w, angle_diff, conf_ok = None, None, None, None, False

        if has_direct_kpts:
            rel_nose_x, rel_nose_y, shoulder_w, angle_diff, conf_ok = self._pose_suspicion_with_angle(
                person_kpts, conf_min=settings.LANDMARK_MIN_VISIBILITY
            )

        if not conf_ok or rel_nose_x is None:
            # Fallback to SolvePnP geometric approach if direct keypoints missing
            return self._fallback_pnp_processing(
                full_frame_bgr, bbox_xyxy_norm, track_id, frame_id, captured_at_ms,
                detection_conf, state, activity, w_frame, h_frame
            )

        # 3. Detect arm raised / hand actions (COCO: 5=ls, 6=rs, 9=lw, 10=rw)
        shoulder_tilt = 0.0
        if len(person_kpts) >= 7 and shoulder_w > 0:
            lsy = float(person_kpts[5][1])
            rsy = float(person_kpts[6][1])
            shoulder_tilt = abs(rsy - lsy) / shoulder_w
        state.shoulder_tilt = shoulder_tilt
        state.is_leaning = shoulder_tilt > 0.20

        arm_raised = False
        if len(person_kpts) > 10 and shoulder_w > 0:
            lsy = float(person_kpts[5][1])
            rsy = float(person_kpts[6][1])
            lw_y, lw_c = float(person_kpts[9][1]), float(person_kpts[9][2]) if len(person_kpts[9]) > 2 else 1.0
            rw_y, rw_c = float(person_kpts[10][1]), float(person_kpts[10][2]) if len(person_kpts[10]) > 2 else 1.0
            if (lw_c >= 0.3 and lw_y < (lsy - 0.08 * shoulder_w)) or (rw_c >= 0.3 and rw_y < (rsy - 0.08 * shoulder_w)):
                arm_raised = True
                activity = "hand_raised"

        yaw_deg = float(angle_diff) * (180.0 / math.pi)

        # Gap Continuity Check
        if state.last_valid_time_ms is not None:
            delta_time_s = (captured_at_ms - state.last_valid_time_ms) / 1000.0
            if delta_time_s > settings.GAP_RESET_TIMEOUT_S:
                state.reset_behavior_timers()
        state.last_valid_time_ms = captured_at_ms

        # 4. Phase 1: Calibration (EMA Auto-Calibration per student)
        if not state.is_calibrated:
            alpha = 0.10
            if state.base_nose_x is None:
                state.base_nose_x = float(rel_nose_x)
                state.base_nose_y = float(rel_nose_y)
                state.baseline_yaw = float(yaw_deg)
            else:
                state.base_nose_x = (1.0 - alpha) * state.base_nose_x + alpha * float(rel_nose_x)
                state.base_nose_y = (1.0 - alpha) * state.base_nose_y + alpha * float(rel_nose_y)
                state.baseline_yaw = (1.0 - alpha) * state.baseline_yaw + alpha * float(yaw_deg)

            state.calibration_samples += 1
            if state.calibration_samples >= settings.CALIBRATION_SAMPLES:
                state.is_calibrated = True

            return TrackResult(
                track_id=track_id,
                bbox_xyxy_norm=bbox_xyxy_norm,
                detection_confidence=round(detection_conf, 2),
                pose_valid=True,
                pose_sample_frame=frame_id,
                calibration_samples=state.calibration_samples,
                status="CALIBRATING",
                reasons=[],
                yaw_delta_deg=0.0,
                nose_drop_ratio=0.0,
                turning_duration_ms=0,
                bending_duration_ms=0,
                progress_percent=round((state.calibration_samples / settings.CALIBRATION_SAMPLES) * 100.0, 1),
                activity=activity,
                suspicion_score=0,
                suspicion_level="NORMAL",
                shoulder_tilt=round(shoulder_tilt, 2),
                is_leaning=state.is_leaning,
                turn_count_10s=0
            )

        # 5. Phase 2: Posture Evaluation (dyingangell/Cheating-detection-YOLO)
        delta_yaw = yaw_deg - state.baseline_yaw
        lateral_dev = abs(float(rel_nose_x) - float(state.base_nose_x))
        depth_dev = abs(float(rel_nose_y) - float(state.base_nose_y))
        dist = math.hypot(lateral_dev, depth_dev)
        nose_drop_ratio = max(0.0, float(rel_nose_y) - float(state.base_nose_y))

        # Foreshortening compensation for camera angle
        y_frac = min(1.0, max(0.0, box_cy / max(1.0, float(h_frame))))
        foreshortening_factor = 1.0 + float(settings.POSE_FORESHORTENING_STRENGTH) * y_frac
        effective_base_radius = float(settings.POSE_BASE_RADIUS) * foreshortening_factor

        # Forward writing suppression: paper-bending is depth-dominant, not cheating
        if depth_dev > lateral_dev * float(settings.POSE_DEPTH_SUPPRESS_RATIO):
            effective_lateral = lateral_dev * 0.3
        else:
            effective_lateral = lateral_dev

        lateral_excess = max(0.0, effective_lateral - effective_base_radius)
        abs_delta_angle = abs(math.radians(delta_yaw))
        angle_excess = max(0.0, abs_delta_angle - float(settings.POSE_ANGLE_BASE_RAD))
        combined_excess = max(float(lateral_excess), float(settings.POSE_ANGLE_WEIGHT) * float(angle_excess))

        suspicious = False
        if dist > float(settings.POSE_MAX_AWAY_DIST):
            state.is_away = True
            suspicious = False
        elif state.is_away and dist <= effective_base_radius:
            state.is_away = False
            state.base_nose_x = float(rel_nose_x)
            state.base_nose_y = float(rel_nose_y)
            state.score_s = 0.0
            suspicious = False
        elif combined_excess > 0.0 and not state.is_away:
            suspicious = True

        # Temporal warning score accumulation
        if is_walking:
            state.score_s = max(0.0, state.score_s - dt * 2.0)
        elif suspicious:
            add = float(settings.POSE_SCORE_K) * float(combined_excess) * dt
            state.score_s = min(15.0, state.score_s + add)
        else:
            state.score_s = max(0.0, state.score_s - dt * 0.2)

        # 6. Flag triggers and durations
        is_turning = abs(delta_yaw) > settings.YAW_THRESHOLD_DEG or lateral_excess > 0.06
        is_bending = nose_drop_ratio > settings.NOSE_DROP_RATIO_THRESHOLD

        if is_turning:
            if not state.was_turning:
                state.turn_events.append(captured_at_ms)
            if state.turning_start_time_ms is None:
                state.turning_start_time_ms = captured_at_ms
            state.turning_duration_ms = captured_at_ms - state.turning_start_time_ms
        else:
            state.turning_start_time_ms = None
            state.turning_duration_ms = 0
        state.was_turning = is_turning

        if is_bending:
            if state.bending_start_time_ms is None:
                state.bending_start_time_ms = captured_at_ms
            state.bending_duration_ms = captured_at_ms - state.bending_start_time_ms
        else:
            state.bending_start_time_ms = None
            state.bending_duration_ms = 0

        # Frequency of turning in the last 10 seconds
        turn_count_10s = sum(1 for t_ms in state.turn_events if captured_at_ms - t_ms <= 10000)

        threshold = float(settings.POSE_WARN_THRESHOLD_S)
        reasons: List[BehaviorReason] = []

        if state.score_s >= threshold or state.turning_duration_ms >= int(settings.REVIEW_TRIGGER_DURATION_S * 1000):
            status: TrackStatus = "REVIEW"
            if is_turning:
                reasons.append("TURNING")
            if is_bending:
                reasons.append("BENDING")
            if not reasons:
                reasons.append("TURNING")
        elif state.score_s > 0.6 or suspicious or state.turning_duration_ms > 400:
            status = "OBSERVING"
            if is_turning:
                reasons.append("TURNING")
            if is_bending:
                reasons.append("BENDING")
        else:
            status = "WITHIN_THRESHOLDS"

        # Calculate Hazard Meter Suspicion Score (0 to 100)
        suspicion_score = min(100, int((state.score_s / max(0.1, threshold)) * 100))
        if status == "REVIEW":
            suspicion_score = max(80, suspicion_score)

        if suspicion_score >= 80:
            suspicion_level = "ALERT"
        elif suspicion_score >= 50:
            suspicion_level = "WARNING"
        elif suspicion_score >= 25:
            suspicion_level = "ATTENTION"
        else:
            suspicion_level = "NORMAL"

        state.suspicion_score = suspicion_score
        state.suspicion_level = suspicion_level
        state.last_yaw = yaw_deg
        state.last_nose_drop_ratio = nose_drop_ratio
        state.last_status = status

        return TrackResult(
            track_id=track_id,
            bbox_xyxy_norm=bbox_xyxy_norm,
            detection_confidence=round(detection_conf, 2),
            pose_valid=True,
            pose_sample_frame=frame_id,
            calibration_samples=settings.CALIBRATION_SAMPLES,
            status=status,
            reasons=reasons,
            yaw_delta_deg=round(delta_yaw, 1),
            nose_drop_ratio=round(nose_drop_ratio, 3),
            turning_duration_ms=state.turning_duration_ms,
            bending_duration_ms=state.bending_duration_ms,
            progress_percent=100.0,
            activity=activity,
            suspicion_score=suspicion_score,
            suspicion_level=suspicion_level,
            shoulder_tilt=round(shoulder_tilt, 2),
            is_leaning=state.is_leaning,
            turn_count_10s=turn_count_10s
        )

    def _fallback_pnp_processing(
        self,
        full_bgr: Any,
        bbox_xyxy_norm: Tuple[float, float, float, float],
        track_id: int,
        frame_id: int,
        captured_at_ms: int,
        detection_conf: float,
        state: CandidateTrackState,
        activity: str,
        w_frame: int,
        h_frame: int
    ) -> TrackResult:
        """Fallback processing using SolvePnP if pose keypoints were not passed."""
        x1_n, y1_n, x2_n, y2_n = bbox_xyxy_norm
        pad_x = (x2_n - x1_n) * settings.ROI_EXPAND_RATIO
        pad_y = (y2_n - y1_n) * settings.ROI_EXPAND_RATIO

        x1_c = max(0, int((x1_n - pad_x) * w_frame))
        y1_c = max(0, int((y1_n - pad_y) * h_frame))
        x2_c = min(w_frame, int((x2_n + pad_x) * w_frame))
        y2_c = min(h_frame, int((y2_n + pad_y) * h_frame))
        w_c = x2_c - x1_c
        h_c = y2_c - y1_c

        if w_c < 20 or h_c < 20:
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state, activity)

        center_x = x1_c + w_c * 0.5
        top_y = y1_c + h_c * 0.18
        nose_y = top_y + h_c * 0.12
        chin_y = nose_y + h_c * 0.15

        pts_2d = np.array([
            [center_x, nose_y],
            [center_x, chin_y],
            [center_x - w_c * 0.15, top_y + h_c * 0.05],
            [center_x + w_c * 0.15, top_y + h_c * 0.05],
            [center_x - w_c * 0.10, nose_y + h_c * 0.08],
            [center_x + w_c * 0.10, nose_y + h_c * 0.08]
        ], dtype=np.float64)

        pnp_result = estimate_head_pose_pnp(pts_2d, w_frame, h_frame)
        if pnp_result is None:
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state, activity)

        yaw_deg, _, _ = pnp_result

        if not state.is_calibrated:
            state.calibration_yaws.append(yaw_deg)
            state.calibration_nose_ys.append(float(nose_y))
            state.calibration_samples += 1

            if state.calibration_samples >= settings.CALIBRATION_SAMPLES:
                state.baseline_yaw = statistics.median(state.calibration_yaws)
                med_nose_y = float(statistics.median(state.calibration_nose_ys))
                state.baseline_nose_y = med_nose_y
                state.base_nose_y = med_nose_y
                state.base_nose_x = 0.0
                state.is_calibrated = True

            return TrackResult(
                track_id=track_id,
                bbox_xyxy_norm=bbox_xyxy_norm,
                detection_confidence=round(detection_conf, 2),
                pose_valid=True,
                pose_sample_frame=frame_id,
                calibration_samples=state.calibration_samples,
                status="CALIBRATING",
                reasons=[],
                yaw_delta_deg=0.0,
                nose_drop_ratio=0.0,
                turning_duration_ms=0,
                bending_duration_ms=0,
                progress_percent=round((state.calibration_samples / settings.CALIBRATION_SAMPLES) * 100.0, 1),
                activity=activity,
                suspicion_score=0,
                suspicion_level="NORMAL",
                shoulder_tilt=0.0,
                is_leaning=False,
                turn_count_10s=0
            )

        baseline_yaw = getattr(state, "baseline_yaw", 0.0) or 0.0
        delta_yaw = compute_delta_yaw(yaw_deg, baseline_yaw)
        base_nose_y = getattr(state, "baseline_nose_y", None)
        if base_nose_y is None:
            base_nose_y = getattr(state, "base_nose_y", None)
        if base_nose_y is None:
            base_nose_y = float(nose_y)
        nose_drop_ratio = max(0.0, (nose_y - base_nose_y) / float(h_frame))
        is_turning = abs(delta_yaw) > settings.YAW_THRESHOLD_DEG
        is_bending = nose_drop_ratio > settings.NOSE_DROP_RATIO_THRESHOLD

        if is_turning:
            if not state.was_turning:
                state.turn_events.append(captured_at_ms)
            if state.turning_start_time_ms is None:
                state.turning_start_time_ms = captured_at_ms
            state.turning_duration_ms = captured_at_ms - state.turning_start_time_ms
        else:
            state.turning_start_time_ms = None
            state.turning_duration_ms = 0
        state.was_turning = is_turning

        reasons = []
        if state.turning_duration_ms >= int(settings.REVIEW_TRIGGER_DURATION_S * 1000):
            status = "REVIEW"
            reasons.append("TURNING")
        elif state.turning_duration_ms > 300:
            status = "OBSERVING"
            reasons.append("TURNING")
        else:
            status = "WITHIN_THRESHOLDS"

        return TrackResult(
            track_id=track_id,
            bbox_xyxy_norm=bbox_xyxy_norm,
            detection_confidence=round(detection_conf, 2),
            pose_valid=True,
            pose_sample_frame=frame_id,
            calibration_samples=settings.CALIBRATION_SAMPLES,
            status=status,
            reasons=reasons,
            yaw_delta_deg=round(delta_yaw, 1),
            nose_drop_ratio=round(nose_drop_ratio, 3),
            turning_duration_ms=state.turning_duration_ms,
            bending_duration_ms=0,
            progress_percent=100.0,
            activity=activity,
            suspicion_score=80 if status == "REVIEW" else (35 if status == "OBSERVING" else 5),
            suspicion_level="ALERT" if status == "REVIEW" else ("ATTENTION" if status == "OBSERVING" else "NORMAL"),
            shoulder_tilt=0.0,
            is_leaning=False,
            turn_count_10s=0
        )

    def _build_unavailable_result(
        self,
        track_id: int,
        bbox_xyxy_norm: Tuple[float, float, float, float],
        detection_conf: float,
        frame_id: int,
        state: CandidateTrackState,
        activity: str = "attentive"
    ) -> TrackResult:
        state.reset_behavior_timers()
        return TrackResult(
            track_id=track_id,
            bbox_xyxy_norm=bbox_xyxy_norm,
            detection_confidence=round(detection_conf, 2),
            pose_valid=False,
            pose_sample_frame=frame_id,
            calibration_samples=state.calibration_samples if not state.is_calibrated else settings.CALIBRATION_SAMPLES,
            status="POSE_UNAVAILABLE",
            reasons=[],
            yaw_delta_deg=0.0,
            nose_drop_ratio=0.0,
            turning_duration_ms=0,
            bending_duration_ms=0,
            progress_percent=0.0,
            activity=activity,
            suspicion_score=0,
            suspicion_level="UNKNOWN",
            shoulder_tilt=0.0,
            is_leaning=False,
            turn_count_10s=0
        )
