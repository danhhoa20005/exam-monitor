"""
Tracking Core Module for YOLOv8 and ByteTrack Integration.
Processes incoming JPEG frames, performs object detection, tracks candidates,
and coordinates posture behavior analysis.
"""
import os
import time
import base64
try:
    import numpy as np
    import cv2
except ImportError:
    np = None
    cv2 = None
from typing import List, Tuple, Optional

from app.config import settings
from app.protocol import FrameResult, TrackResult
from app.inference.pose_behavior import PoseBehaviorEngine
from app.inference.events import EventManager

class SessionInferencePipeline:
    """End-to-end inference pipeline for a single active monitoring session."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.pose_engine = PoseBehaviorEngine()
        self.event_manager = EventManager(session_id)
        self.yolo_model = None
        self.is_pose_model = False
        self.is_custom_student_model = False
        self._init_yolo()

    def _init_yolo(self):
        """Initialize YOLO11-Pose detector (from dyingangell/Cheating-detection-YOLO) or custom weights."""
        pose_model_path = str(settings.YOLO_POSE_MODEL_PATH)
        custom_model_path = str(settings.YOLO_MODEL_PATH)
        fallback_path = str(settings.FALLBACK_YOLO_PATH)

        target_path = None
        if os.path.exists(pose_model_path):
            target_path = pose_model_path
            self.is_pose_model = True
            print(f"[OK] Loading YOLO11-Pose model: {pose_model_path}")
        elif os.path.exists(custom_model_path):
            target_path = custom_model_path
            self.is_custom_student_model = True
            print(f"[OK] Loading custom trained YOLO model: {custom_model_path}")
        elif os.path.exists(fallback_path):
            target_path = fallback_path
            print(f"[INFO] Using fallback YOLO model: {fallback_path}")
        else:
            print(f"[INFO] Downloading YOLO11-Pose weights to {pose_model_path}...")
            try:
                from models.download_models import download_yolo_pose_model
                download_yolo_pose_model()
                if os.path.exists(pose_model_path):
                    target_path = pose_model_path
                    self.is_pose_model = True
            except Exception as dl_err:
                print(f"[WARN] Could not auto-download pose model: {dl_err}")

        if target_path:
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(target_path)
                self.is_pose_model = getattr(self.yolo_model, 'task', '') == 'pose' or 'pose' in str(target_path).lower()
                print(f"[OK] Model loaded into memory successfully: {target_path} (is_pose={self.is_pose_model}, classes={self.yolo_model.names})")
            except Exception as e:
                print(f"[WARN] Failed to load YOLO from {target_path}: {e}")
                self.yolo_model = None

    def process_frame(
        self,
        frame_id: int,
        captured_at_ms: int,
        width: int,
        height: int,
        jpeg_base64: str
    ) -> FrameResult:
        """
        Decode JPEG, run YOLO-Pose detection, track candidates, analyze posture, and update events.
        """
        t0 = time.perf_counter()

        # 1. Decode JPEG image
        try:
            image_data = base64.b64decode(jpeg_base64)
            np_arr = np.frombuffer(image_data, np.uint8)
            frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                raise ValueError("cv2.imdecode returned None")
        except Exception as e:
            return FrameResult(
                session_id=self.session_id,
                frame_id=frame_id,
                captured_at_ms=captured_at_ms,
                processing_ms=1,
                yolo_ms=0,
                pose_ms=0,
                frame_size=(width, height),
                tracks=[],
                new_event_ids=[]
            )

        h_frame, w_frame = frame_bgr.shape[:2]

        # 2. YOLO11-Pose Detection & ByteTrack
        t_yolo_start = time.perf_counter()
        detections: List[Tuple[int, Tuple[float, float, float, float], float, str, Optional[Any]]] = []

        if self.yolo_model is not None:
            try:
                bytetrack_cfg = str(settings.BYTETRACK_CONFIG_PATH) if os.path.exists(settings.BYTETRACK_CONFIG_PATH) else "bytetrack.yaml"
                results = self.yolo_model.track(
                    frame_bgr,
                    persist=True,
                    tracker=bytetrack_cfg,
                    verbose=False,
                    conf=0.30
                )

                if results and len(results) > 0 and results[0].boxes is not None:
                    res = results[0]
                    boxes = res.boxes
                    has_kpts = (
                        res.keypoints is not None 
                        and hasattr(res.keypoints, 'data') 
                        and res.keypoints.data is not None
                    )

                    for i, box in enumerate(boxes):
                        cls_id = int(box.cls[0].item())
                        names = self.yolo_model.names
                        cls_name = names.get(cls_id, "") if isinstance(names, dict) else (
                            names[cls_id] if 0 <= cls_id < len(names) else ""
                        )
                        normalized_name = str(cls_name).strip().lower().replace("-", "_").replace(" ", "_")
                        is_single_class = len(names) == 1
                        is_person_class = normalized_name in {
                            "person", "student", "student_v1", "candidate", "human", "attentive", "inattentive", "hand_raised"
                        } or cls_id in (0, 1, 2)

                        if is_single_class or is_person_class or cls_id == 0 or self.is_pose_model:
                            track_id = int(box.id[0].item()) if box.id is not None else (i + 1)
                            conf = float(box.conf[0].item())
                            xyxy = box.xyxy[0].tolist()
                            
                            norm_bbox = (
                                xyxy[0] / float(w_frame),
                                xyxy[1] / float(h_frame),
                                xyxy[2] / float(w_frame),
                                xyxy[3] / float(h_frame)
                            )

                            kpts = None
                            if has_kpts and len(res.keypoints.data) > i:
                                try:
                                    kpts = res.keypoints.data[i].cpu().numpy()
                                except Exception:
                                    kpts = None

                            detections.append((track_id, norm_bbox, conf, normalized_name, kpts))
            except Exception as e:
                print(f"[WARN] YOLO tracking error: {e}")
        else:
            center_bbox = (0.25, 0.20, 0.75, 0.90)
            detections.append((1, center_bbox, 0.90, "attentive", None))

        t_yolo_end = time.perf_counter()
        yolo_ms = int((t_yolo_end - t_yolo_start) * 1000)

        # 3. Pose Behavior Estimation per Candidate ROI
        t_pose_start = time.perf_counter()
        track_results: List[TrackResult] = []
        active_track_ids = [d[0] for d in detections]
        self.pose_engine.remove_lost_tracks(active_track_ids)

        for track_id, bbox_norm, conf, act_name, kpts in detections:
            try:
                res = self.pose_engine.process_student_roi(
                    full_frame_bgr=frame_bgr,
                    bbox_xyxy_norm=bbox_norm,
                    track_id=track_id,
                    frame_id=frame_id,
                    captured_at_ms=captured_at_ms,
                    detection_conf=conf,
                    person_kpts=kpts,
                    activity=act_name if act_name in ["attentive", "hand_raised", "inattentive"] else "attentive"
                )
                track_results.append(res)
            except Exception as e:
                print(f"[WARN] Error analyzing pose for track {track_id}: {e}")

        t_pose_end = time.perf_counter()
        pose_ms = int((t_pose_end - t_pose_start) * 1000)

        # 4. Event State Machine Aggregation
        new_event_ids = self.event_manager.process_track_alerts(
            tracks=track_results,
            captured_at_ms=captured_at_ms
        )

        total_processing_ms = int((time.perf_counter() - t0) * 1000)

        return FrameResult(
            session_id=self.session_id,
            frame_id=frame_id,
            captured_at_ms=captured_at_ms,
            processing_ms=total_processing_ms,
            yolo_ms=yolo_ms,
            pose_ms=pose_ms,
            frame_size=(w_frame, h_frame),
            tracks=track_results,
            new_event_ids=new_event_ids
        )

    def close(self):
        """Release session resources."""
        now_ms = int(time.time() * 1000)
        self.event_manager.close_all_on_stop(now_ms)
        self.pose_engine.reset_session()
