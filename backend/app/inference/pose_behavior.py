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
import statistics
import time
try:
    import numpy as np
    import cv2
except ImportError:
    np = None
    cv2 = None
from typing import Dict, List, Optional, Tuple, Any

from app.config import settings
from app.protocol import TrackStatus, BehaviorReason, TrackResult
from app.inference.pnp_head_pose import compute_delta_yaw
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
        self.yaw_calib_samples: int = 0            # calibration samples where both ears were visible
        self.baseline_torso_angle: Optional[float] = None
        self.calibration_yaws: List[float] = []      # head yaw, only frames where it was measurable
        self.calibration_nose_xs: List[float] = []
        self.calibration_nose_ys: List[float] = []
        self.calibration_torso: List[float] = []

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
        self.turn_prob_ema: Optional[float] = None   # smoothed P(turn) from the crop classifier
        self.calibration_turn_probs: List[float] = []
        self.turn_prob_base: Optional[float] = None  # this student's usual P(turn) (camera angle, seating)
        self.phone_ema: float = 0.0                   # smoothed "phone next to a wrist" flag
        self.phone_start_ms: Optional[int] = None
        self.phone_duration_ms: int = 0

    def reset_calibration(self):
        """Reset ongoing calibration samples if track was interrupted."""
        self.calibration_yaws.clear()
        self.calibration_nose_xs.clear()
        self.calibration_nose_ys.clear()
        self.calibration_torso.clear()
        self.calibration_turn_probs.clear()
        self.turn_prob_base = None
        self.base_nose_x = None
        self.base_nose_y = None
        self.baseline_nose_y = None
        self.baseline_yaw = 0.0
        self.yaw_calib_samples = 0
        self.baseline_torso_angle = None
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
    PROFILE_YAW_DEG = 60.0   # yaw at which the far ear typically disappears
    # Measured at 960px: classroom CCTV shoulders p90 = 70px, DS-03 close-up p10 = 119px
    PROFILE_MIN_SHOULDER_FRAC = 0.09
    # |nose - eye midpoint| / eye distance on one-ear frames: DS-03 looks p10 = 0.13, cap-brim occlusion p90 = 0.04
    PROFILE_MIN_EYE_OFFSET = 0.10
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
    def _head_yaw_from_face(person_kpts: Any, conf_min: float = 0.3, frame_w: Optional[float] = None) -> Optional[float]:
        """
        Head yaw proxy (degrees) from nose position relative to the ear midpoint.
        COCO keypoints: 0: nose, 3: left_ear, 4: right_ear
        The nose sits ~1.33x the half ear-distance in front of the ear axis, so
        (nose_x - ear_mid_x) / half_ear_dist ~= 1.33 * tan(yaw). Unlike the
        nose-vs-torso angle, this is insensitive to bowing the head over the desk.
        When the head turns far enough, the far ear is occluded: that IS the turned-head
        state, so a confident nose + one confident ear + one hidden ear returns a profile
        yaw (+-PROFILE_YAW_DEG) on the side of the hidden ear. Ear confidence is only
        trustworthy when the person is large enough (shoulders >= PROFILE_MIN_SHOULDER_FRAC
        of frame_w): in wide classroom shots (~40px shoulders at 960px) ears flicker
        between visible and hidden without any head movement.
        Returns None when the nose or both ears are not visible.
        """
        if person_kpts is None or len(person_kpts) < 5:
            return None
        nose, l_ear, r_ear = person_kpts[0], person_kpts[3], person_kpts[4]
        nose_c, l_c, r_c = [float(p[2]) if len(p) > 2 else 1.0 for p in (nose, l_ear, r_ear)]
        if nose_c < conf_min:
            return None
        if min(l_c, r_c) < conf_min:
            visible = l_ear if l_c >= r_c else r_ear
            if max(l_c, r_c) < 0.5 or min(l_c, r_c) >= conf_min:
                return None
            if frame_w and len(person_kpts) > 6:
                shoulder_w = abs(float(person_kpts[5][0]) - float(person_kpts[6][0]))
                if shoulder_w < PoseBehaviorEngine.PROFILE_MIN_SHOULDER_FRAC * frame_w:
                    return None
            # An ear can also vanish behind a cap brim, hair or hand without any turn
            # (DS-03 v_c5_s7_s8). Confirm with the eyes: a turned nose leaves the eye midpoint.
            l_eye, r_eye = person_kpts[1], person_kpts[2]
            eye_c = min(float(l_eye[2]), float(r_eye[2])) if len(l_eye) > 2 else 1.0
            eye_dist = abs(float(l_eye[0]) - float(r_eye[0]))
            if eye_c < conf_min or eye_dist < 1.0:
                return None
            eye_offset = (float(nose[0]) - (float(l_eye[0]) + float(r_eye[0])) / 2.0) / eye_dist
            if abs(eye_offset) < PoseBehaviorEngine.PROFILE_MIN_EYE_OFFSET:
                return None
            # the nose has swung away from the visible ear, towards the hidden one
            return PoseBehaviorEngine.PROFILE_YAW_DEG * (1.0 if float(nose[0]) > float(visible[0]) else -1.0)
        half_ear = abs(float(l_ear[0]) - float(r_ear[0])) / 2.0
        if half_ear < 1.0:
            return None
        ratio = (float(nose[0]) - (float(l_ear[0]) + float(r_ear[0])) / 2.0) / half_ear
        return math.degrees(math.atan(0.75 * ratio))

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
        activity: str = "attentive",
        turn_prob: Optional[float] = None,
        phone_seen: Optional[bool] = None
    ) -> TrackResult:
        """
        Process single tracked candidate using YOLO11-Pose keypoints and Cheating-detection-YOLO algorithm.
        turn_prob: P(turn) from the team's crop classifier for this frame, if loaded.
        phone_seen: whether the phone detector saw a phone next to this student's wrist, if loaded.
        """
        h_frame, w_frame = full_frame_bgr.shape[:2]
        x1_n, y1_n, x2_n, y2_n = bbox_xyxy_norm
        
        state = self.get_or_create_state(track_id)
        now_ts = captured_at_ms / 1000.0
        dt = max(0.0, min(0.25, float(now_ts - state.last_ts))) if state.last_ts > 0 else 0.05
        state.last_ts = now_ts

        # Smooth the classifier output so a single-frame spike cannot start a turning episode
        if turn_prob is not None:
            if state.turn_prob_ema is None:
                state.turn_prob_ema = float(turn_prob)
            else:
                a = settings.TURN_CLS_EMA_ALPHA
                state.turn_prob_ema = (1.0 - a) * state.turn_prob_ema + a * float(turn_prob)
        ai_turn_prob = round(state.turn_prob_ema, 2) if state.turn_prob_ema is not None else None

        # Phone needs no posture baseline, so it is tracked from the first frame (also while calibrating)
        if phone_seen is not None:
            a = settings.PHONE_EMA_ALPHA
            state.phone_ema = (1.0 - a) * state.phone_ema + a * (1.0 if phone_seen else 0.0)
            if state.phone_ema > settings.PHONE_EMA_ON:
                if state.phone_start_ms is None:
                    state.phone_start_ms = captured_at_ms
                state.phone_duration_ms = captured_at_ms - state.phone_start_ms
            else:
                state.phone_start_ms = None
                state.phone_duration_ms = 0
        phone_on = state.phone_ema > settings.PHONE_EMA_ON
        phone_active = state.phone_duration_ms >= int(settings.PHONE_TRIGGER_S * 1000)

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
            # No reliable keypoints: report honestly instead of guessing a head pose from the bbox
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state, activity)

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

        head_yaw = self._head_yaw_from_face(person_kpts, conf_min=settings.LANDMARK_MIN_VISIBILITY, frame_w=w_frame)
        torso_angle_deg = float(angle_diff) * (180.0 / math.pi)

        # Gap Continuity Check
        if state.last_valid_time_ms is not None:
            delta_time_s = (captured_at_ms - state.last_valid_time_ms) / 1000.0
            if delta_time_s > settings.GAP_RESET_TIMEOUT_S:
                state.reset_behavior_timers()
        state.last_valid_time_ms = captured_at_ms

        # 4. Phase 1: Calibration. Baseline = per-quantity median of the calibration samples,
        # so a glance covering less than half of the window (DS-03 v_c3_s2) cannot shift it.
        if not state.is_calibrated:
            state.calibration_nose_xs.append(float(rel_nose_x))
            state.calibration_nose_ys.append(float(rel_nose_y))
            state.calibration_torso.append(torso_angle_deg)
            if head_yaw is not None:
                state.calibration_yaws.append(head_yaw)
            if turn_prob is not None:
                state.calibration_turn_probs.append(float(turn_prob))

            state.calibration_samples += 1
            if state.calibration_samples >= settings.CALIBRATION_SAMPLES:
                state.base_nose_x = statistics.median(state.calibration_nose_xs)
                state.base_nose_y = statistics.median(state.calibration_nose_ys)
                # angles wrap at +-180: take the median of offsets from the first sample
                ref = state.calibration_torso[0]
                state.baseline_torso_angle = ref + statistics.median(
                    compute_delta_yaw(a, ref) for a in state.calibration_torso)
                if state.calibration_yaws:
                    state.baseline_yaw = statistics.median(state.calibration_yaws)
                state.yaw_calib_samples = len(state.calibration_yaws)
                if state.calibration_turn_probs:
                    state.turn_prob_base = statistics.median(state.calibration_turn_probs)
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
        # Head yaw only counts when both this frame and the calibration saw the ears
        if head_yaw is not None and state.yaw_calib_samples > 0:
            delta_yaw = compute_delta_yaw(head_yaw, state.baseline_yaw)
        else:
            delta_yaw = 0.0
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
        abs_delta_angle = abs(math.radians(compute_delta_yaw(torso_angle_deg, state.baseline_torso_angle)))
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
        # The classifier only sees appearance: a student seated side-on to the camera looks "turned"
        # all the time (classroom.mp4 P(turn)~0.9 while writing), so require a rise above their own baseline.
        ai_turning = (state.turn_prob_ema is not None
                      and state.turn_prob_ema > settings.TURN_CLS_THRESHOLD
                      and state.turn_prob_ema - (state.turn_prob_base or 0.0) >= settings.TURN_CLS_MARGIN)
        is_turning = abs(delta_yaw) > settings.YAW_THRESHOLD_DEG or lateral_excess > 0.06 or ai_turning
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

        if (state.score_s >= threshold or state.turning_duration_ms >= int(settings.REVIEW_TRIGGER_DURATION_S * 1000)
                or phone_active):
            status: TrackStatus = "REVIEW"
            if is_turning:
                reasons.append("TURNING")
            if is_bending:
                reasons.append("BENDING")
            if phone_on:
                reasons.append("PHONE")
            if not reasons:
                reasons.append("PHONE" if phone_active else "TURNING")
        elif state.score_s > 0.6 or suspicious or state.turning_duration_ms > 400 or phone_on:
            status = "OBSERVING"
            if is_turning:
                reasons.append("TURNING")
            if is_bending:
                reasons.append("BENDING")
            if phone_on:
                reasons.append("PHONE")
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
        state.last_yaw = head_yaw if head_yaw is not None else state.last_yaw
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
            turn_count_10s=turn_count_10s,
            ai_turn_prob=ai_turn_prob
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
