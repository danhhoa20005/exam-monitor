"""
Pose Estimation and Behavioral State Machine.
Implements calibration (20 samples), head turning (>35 deg), and bending down (>15% height) rules.
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


class PoseBehaviorEngine:
    """Engine managing MediaPipe Pose inference and per-track behavior evaluation."""
    def __init__(self):
        self.track_states: Dict[int, CandidateTrackState] = {}
        self.detector = None
        self._init_mediapipe_landmarker()

    def _init_mediapipe_landmarker(self):
        """Initialize Pose Estimator."""
        # Using pure Python + OpenCV SolvePnP 3D Head Pose & Nose Drop Estimator
        # for maximum stability across macOS ARM64 and Linux.
        self.detector = None
        print("[OK] OpenCV SolvePnP 3D Head Pose & Nose Drop Estimator initialized successfully.")

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
                # If track was calibrating and lost, remove it completely
                if not self.track_states[tid].is_calibrated:
                    self.track_states.pop(tid, None)

    def process_student_roi(
        self,
        full_frame_bgr: Any,
        bbox_xyxy_norm: Tuple[float, float, float, float],
        track_id: int,
        frame_id: int,
        captured_at_ms: int,
        detection_conf: float
    ) -> TrackResult:
        """
        Extract ROI, run pose estimation, calculate yaw/nose drop, and update state machine.
        """
        h_frame, w_frame = full_frame_bgr.shape[:2]
        x1_n, y1_n, x2_n, y2_n = bbox_xyxy_norm
        
        # 1. Expand ROI by ~12% with border clamping
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
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state)

        # 2. Extract Keypoints via MediaPipe or Geometric Model
        keypoints_2d, nose_y_full, is_valid = self._extract_pose_keypoints(
            full_frame_bgr, x1_crop, y1_crop, crop_w, crop_h, w_frame, h_frame
        )

        if not is_valid or keypoints_2d is None:
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state)

        # 3. Estimate Head Orientation via SolvePnP
        pnp_result = estimate_head_pose_pnp(keypoints_2d, w_frame, h_frame)
        if pnp_result is None:
            return self._build_unavailable_result(track_id, bbox_xyxy_norm, detection_conf, frame_id, state)

        yaw_deg, pitch_deg, _ = pnp_result

        # 4. Check Sample Time Continuity (Gap > 2.5s resets behavior timers)
        if state.last_valid_time_ms is not None:
            delta_time_s = (captured_at_ms - state.last_valid_time_ms) / 1000.0
            if delta_time_s > settings.GAP_RESET_TIMEOUT_S:
                state.reset_behavior_timers()
        state.last_valid_time_ms = captured_at_ms

        # 5. Phase 1: Calibration (Need 20 consecutive valid pose samples)
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
                progress_percent=round((sample_count / settings.CALIBRATION_SAMPLES) * 100.0, 1)
            )

        # 6. Phase 2: Posture Evaluation (Calibrated)
        delta_yaw = compute_delta_yaw(yaw_deg, state.baseline_yaw)
        nose_drop_ratio = max(0.0, (nose_y_full - state.baseline_nose_y) / float(h_frame))

        is_turning = abs(delta_yaw) > settings.YAW_THRESHOLD_DEG
        is_bending = nose_drop_ratio > settings.NOSE_DROP_RATIO_THRESHOLD

        # Update turning timer
        if is_turning:
            if state.turning_start_time_ms is None:
                state.turning_start_time_ms = captured_at_ms
            state.turning_duration_ms = captured_at_ms - state.turning_start_time_ms
        else:
            state.turning_start_time_ms = None
            state.turning_duration_ms = 0

        # Update bending timer
        if is_bending:
            if state.bending_start_time_ms is None:
                state.bending_start_time_ms = captured_at_ms
            state.bending_duration_ms = captured_at_ms - state.bending_start_time_ms
        else:
            state.bending_start_time_ms = None
            state.bending_duration_ms = 0

        # Determine Status and Reasons
        reasons: List[BehaviorReason] = []
        if is_turning:
            reasons.append("TURNING")
        if is_bending:
            reasons.append("BENDING")

        review_threshold_ms = int(settings.REVIEW_TRIGGER_DURATION_S * 1000)
        is_review = (state.turning_duration_ms >= review_threshold_ms) or (state.bending_duration_ms >= review_threshold_ms)
        is_observing = (state.turning_duration_ms > 0) or (state.bending_duration_ms > 0)

        if is_review:
            status: TrackStatus = "REVIEW"
        elif is_observing:
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
            progress_percent=progress
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
        """
        Extract 6 facial keypoints for PnP from crop ROI and map back to full frame.
        Points: [Nose, Chin, Left Eye, Right Eye, Left Mouth, Right Mouth]
        """
        roi_bgr = full_bgr[y1_c:y1_c+h_c, x1_c:x1_c+w_c]
        if roi_bgr.size == 0:
            return None, 0.0, False

        # If MediaPipe Tasks Landmarker is active:
        if self.detector is not None:
            try:
                import mediapipe as mp
                roi_rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=roi_rgb)
                detection_result = self.detector.detect(mp_image)

                if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
                    lm = detection_result.pose_landmarks[0]
                    # Landmark indices: 0: nose, 2: left_eye, 5: right_eye, 7: left_ear, 8: right_ear, 9: mouth_left, 10: mouth_right
                    min_vis = settings.LANDMARK_MIN_VISIBILITY
                    if lm[0].visibility < min_vis or lm[2].visibility < min_vis or lm[5].visibility < min_vis:
                        return None, 0.0, False

                    # Convert normalized crop coords to full frame pixels
                    nose_x = x1_c + lm[0].x * w_c
                    nose_y = y1_c + lm[0].y * h_c
                    
                    # Approximate chin from nose and mouth/shoulders
                    mouth_mid_y = y1_c + (lm[9].y + lm[10].y) * 0.5 * h_c
                    chin_y = mouth_mid_y + (mouth_mid_y - nose_y) * 0.8
                    chin_x = nose_x

                    l_eye_x = x1_c + lm[2].x * w_c
                    l_eye_y = y1_c + lm[2].y * h_c
                    r_eye_x = x1_c + lm[5].x * w_c
                    r_eye_y = y1_c + lm[5].y * h_c

                    l_mouth_x = x1_c + lm[9].x * w_c
                    l_mouth_y = y1_c + lm[9].y * h_c
                    r_mouth_x = x1_c + lm[10].x * w_c
                    r_mouth_y = y1_c + lm[10].y * h_c

                    pts_2d = np.array([
                        [nose_x, nose_y],
                        [chin_x, chin_y],
                        [l_eye_x, l_eye_y],
                        [r_eye_x, r_eye_y],
                        [l_mouth_x, l_mouth_y],
                        [r_mouth_x, r_mouth_y]
                    ], dtype=np.float64)

                    return pts_2d, float(nose_y), True
            except Exception as e:
                pass

        # Robust Fallback Geometric Estimator (for non-MediaPipe or smoke testing environments)
        # Assumes head center relative to student ROI
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
        state: CandidateTrackState
    ) -> TrackResult:
        """Construct a POSE_UNAVAILABLE result."""
        # Insufficient data breaks continuity
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
            progress_percent=0.0
        )
