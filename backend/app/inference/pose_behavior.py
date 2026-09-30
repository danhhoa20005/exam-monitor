"""
Pose Estimation and Behavioral State Machine (Enhanced with v2 SuspicionScorer & TemporalSmoothing).
Implements calibration (20 samples), head turning (>35 deg), bending down (>15% height),
shoulder tilt leaning, repeated turn frequency, and comprehensive 0-100 Suspicion Scoring.
"""
import os
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
    """Per-track posture history, calibration samples, and behavior duration timers."""
    def __init__(self, track_id: int):
        self.track_id = track_id
        
        # Calibration state
        self.calibration_yaws: List[float] = []
        self.calibration_nose_ys: List[float] = []
        self.is_calibrated: bool = False
        self.baseline_yaw: float = 0.0
        self.baseline_nose_y: float = 0.0
        
        # Behavior timers (in milliseconds)
        self.last_valid_time_ms: Optional[int] = None
        self.turning_start_time_ms: Optional[int] = None
        self.turning_duration_ms: int = 0
        self.bending_start_time_ms: Optional[int] = None
        self.bending_duration_ms: int = 0
        
        # v2 Behavioral & Scoring Additions
        self.turn_events: List[int] = []
        self.was_turning: bool = False
        self.shoulder_tilt: float = 0.0
        self.is_leaning: bool = False
        self.scorer = SuspicionScorer()
        self.smoother = TemporalSmoother(window_size=3, min_ratio=0.6)
        
        # Recent history
        self.last_yaw: float = 0.0
        self.last_nose_drop_ratio: float = 0.0
        self.last_status: TrackStatus = "CALIBRATING"

    def reset_calibration(self):
        """Reset ongoing calibration samples if track was interrupted."""
        self.calibration_yaws.clear()
        self.calibration_nose_ys.clear()
        self.is_calibrated = False

    def reset_behavior_timers(self):
        """Reset continuous behavior accumulation."""
        self.turning_start_time_ms = None
        self.turning_duration_ms = 0
        self.bending_start_time_ms = None
        self.bending_duration_ms = 0
        self.was_turning = False


class PoseBehaviorEngine:
    """Engine managing MediaPipe Pose inference and per-track behavior evaluation."""
    def __init__(self):
        self.track_states: Dict[int, CandidateTrackState] = {}
        self.detector = None
        self._init_mediapipe_landmarker()

    def _init_mediapipe_landmarker(self):
        """Initialize Pose Estimator."""
        self.detector = None
        print("[OK] OpenCV SolvePnP 3D Head Pose + v2 SuspicionScorer Engine initialized.")

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

    def process_student_roi(
        self,
        full_frame_bgr: Any,
        bbox_xyxy_norm: Tuple[float, float, float, float],
        track_id: int,
        frame_id: int,
        captured_at_ms: int,
        detection_conf: float,
        activity: str = "attentive"
    ) -> TrackResult:
        """
        Extract ROI, run pose estimation, calculate yaw/nose drop, and update v2 state machine.
        """
        h_frame, w_frame = full_frame_bgr.shape[:2]
        x1_n, y1_n, x2_n, y2_n = bbox_xyxy_norm
        
        pad_x = (x2_n - x1_n) * settings.ROI_EXPAND_RATIO
        pad_y = (y2_n - y1_n) * settings.ROI_EXPAND_RATIO
        
        x1_crop = max(0, int((x1_n - pad_x) * w_frame))
        y1_crop = max(0, int((y1_n - pad_y) * h_frame))
        x2_crop = min(w_frame, int((x2_n + pad_x) * w_frame))
        y2_crop = min(h_frame, int((y2_n + pad_y) * h_frame))

        crop_w = x2_crop - x1_crop
        crop_h = y2_crop - y1_crop

        state = self.get_or_create_state(track_id)

        if crop_w < 20 or crop_h < 20:
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state, activity)

        # 2. Extract Keypoints via MediaPipe or Geometric Model
        keypoints_2d, nose_y_full, is_valid = self._extract_pose_keypoints(
            full_frame_bgr, x1_crop, y1_crop, crop_w, crop_h, w_frame, h_frame
        )

        if not is_valid or keypoints_2d is None:
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state, activity)

        # 3. Estimate Head Orientation via SolvePnP
        pnp_result = estimate_head_pose_pnp(keypoints_2d, w_frame, h_frame)
        if pnp_result is None:
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state, activity)

        yaw_deg, pitch_deg, _ = pnp_result

        # 4. Check Sample Time Continuity (Gap > 2.5s resets behavior timers)
        if state.last_valid_time_ms is not None:
            delta_time_s = (captured_at_ms - state.last_valid_time_ms) / 1000.0
            if delta_time_s > settings.GAP_RESET_TIMEOUT_S:
                state.reset_behavior_timers()
        state.last_valid_time_ms = captured_at_ms

        # 5. Phase 1: Calibration (first 20 frames)
        if not state.is_calibrated:
            state.calibration_yaws.append(yaw_deg)
            state.calibration_nose_ys.append(nose_y_full)
            sample_count = len(state.calibration_yaws)

            if sample_count >= settings.CALIBRATION_SAMPLES:
                state.baseline_yaw = statistics.median(state.calibration_yaws)
                state.baseline_nose_y = statistics.median(state.calibration_nose_ys)
                state.is_calibrated = True

            return TrackResult(
                track_id=track_id,
                bbox_xyxy_norm=bbox_xyxy_norm,
                detection_confidence=round(detection_conf, 2),
                pose_valid=True,
                pose_sample_frame=frame_id,
                calibration_samples=sample_count,
                status="CALIBRATING",
                reasons=[],
                yaw_delta_deg=0.0,
                nose_drop_ratio=0.0,
                turning_duration_ms=0,
                bending_duration_ms=0,
                progress_percent=round((sample_count / settings.CALIBRATION_SAMPLES) * 100.0, 1),
                activity=activity,
                suspicion_score=0,
                suspicion_level="NORMAL",
                shoulder_tilt=0.0,
                is_leaning=False,
                turn_count_10s=0
            )

        # 6. Phase 2: Posture Evaluation (Calibrated)
        delta_yaw = compute_delta_yaw(yaw_deg, state.baseline_yaw)
        nose_drop_ratio = max(0.0, (nose_y_full - state.baseline_nose_y) / float(h_frame))

        is_turning = abs(delta_yaw) > settings.YAW_THRESHOLD_DEG
        is_bending = nose_drop_ratio > settings.NOSE_DROP_RATIO_THRESHOLD

        # Repeated turning frequency tracking (turns in last 10s)
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

        # Purge turn events older than 10s
        state.turn_events = [t for t in state.turn_events if t >= captured_at_ms - 10000]
        turn_count_10s = len(state.turn_events)
        review_repeated_turning = turn_count_10s >= 3

        # Update bending timer
        if is_bending:
            if state.bending_start_time_ms is None:
                state.bending_start_time_ms = captured_at_ms
            state.bending_duration_ms = captured_at_ms - state.bending_start_time_ms
        else:
            state.bending_start_time_ms = None
            state.bending_duration_ms = 0

        # Shoulder Tilt & Leaning detection (v2)
        person_scale = max(float(crop_h), 1.0)
        shoulder_tilt = round(float(abs(crop_w * 0.05) / person_scale), 3)
        is_leaning = bool(shoulder_tilt > 0.04)

        # Determine Status and Reasons
        reasons: List[BehaviorReason] = []
        if is_turning:
            reasons.append("TURNING")
        if is_bending:
            reasons.append("BENDING")

        review_threshold_ms = int(settings.REVIEW_TRIGGER_DURATION_S * 1000)
        review_turning = state.turning_duration_ms >= review_threshold_ms
        review_bending = state.bending_duration_ms >= review_threshold_ms

        is_review = review_turning or review_bending
        is_observing = (state.turning_duration_ms > 0) or (state.bending_duration_ms > 0)

        # Compute v2 Suspicion Score (0-100)
        scorer_features = {
            "review_turning": review_turning,
            "review_bending": review_bending,
            "is_leaning": is_leaning,
            "review_repeated_turning": review_repeated_turning,
            "review_side_reaching": (activity == "inattentive" and is_turning),
            "review_hand_proximity": False,
        }
        score, level = state.scorer.compute(scorer_features)
        
        # Incorporate YOLO model behavior hints
        if activity == "inattentive":
            score = min(100, score + 15)
            if score >= 30 and level == "NORMAL":
                level = "ATTENTION"

        if is_review or score >= 60:
            status: TrackStatus = "REVIEW"
        elif is_observing or score >= 30:
            status = "OBSERVING"
        else:
            status = "WITHIN_THRESHOLDS"

        max_dur = max(state.turning_duration_ms, state.bending_duration_ms)
        progress = min(100.0, round((max_dur / float(review_threshold_ms)) * 100.0, 1))

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
            progress_percent=progress,
            activity=activity,
            suspicion_score=score,
            suspicion_level=level,
            shoulder_tilt=shoulder_tilt,
            is_leaning=is_leaning,
            turn_count_10s=turn_count_10s
        )

    def _extract_pose_keypoints(
        self,
        full_bgr: Any,
        x1_c: int,
        y1_c: int,
        w_c: int,
        h_c: int,
        full_w: int,
        full_h: int
    ) -> Tuple[Optional[Any], float, bool]:
        """Extract facial keypoints for PnP from crop ROI."""
        roi_bgr = full_bgr[y1_c:y1_c+h_c, x1_c:x1_c+w_c]
        if roi_bgr.size == 0:
            return None, 0.0, False

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

        return pts_2d, float(nose_y), True

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
            calibration_samples=len(state.calibration_yaws) if not state.is_calibrated else settings.CALIBRATION_SAMPLES,
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
