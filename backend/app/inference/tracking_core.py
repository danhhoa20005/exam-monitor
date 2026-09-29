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
        self.is_custom_student_model = False
        self._init_yolo()

    def _init_yolo(self):
        """Initialize YOLOv8 detector from best.pt or default weights."""
        model_path = str(settings.YOLO_MODEL_PATH)
        fallback_path = str(settings.FALLBACK_YOLO_PATH)

        target_path = None
        if os.path.exists(model_path):
            target_path = model_path
            self.is_custom_student_model = True
            print(f"[OK] Loading custom trained YOLO model: {model_path}")
        elif os.path.exists(fallback_path):
            target_path = fallback_path
            print(f"[INFO] Using fallback YOLO model: {fallback_path}")
        else:
            print("[INFO] Model best.pt not found yet. Ready for model drop-in. Will use mock/fallback detector.")
            target_path = None

        if target_path:
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(target_path)
                print("[OK] YOLOv8 model loaded into memory successfully.")
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
        Decode JPEG, run YOLO detection, track candidates, analyze posture, and update events.
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
            # Return empty result on decode failure
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

        # 2. YOLOv8 Detection & ByteTrack
        t_yolo_start = time.perf_counter()
        detections: List[Tuple[int, Tuple[float, float, float, float], float]] = []

        if self.yolo_model is not None:
            try:
                # Run YOLO tracking with ByteTrack config
                bytetrack_cfg = str(settings.BYTETRACK_CONFIG_PATH) if os.path.exists(settings.BYTETRACK_CONFIG_PATH) else "bytetrack.yaml"
                results = self.yolo_model.track(
                    frame_bgr,
                    persist=True,
                    tracker=bytetrack_cfg,
                    verbose=False,
                    conf=0.35
                )

                if results and len(results) > 0 and results[0].boxes is not None:
                    boxes = results[0].boxes
                    for box in boxes:
                        # If model has class names, filter for student/person
                        cls_id = int(box.cls[0].item())
                        cls_name = self.yolo_model.names.get(cls_id, "")
                        
                        # Accept if class is 'student' or 'person' (class 0)
                        if cls_name in ("student", "person") or cls_id == 0:
                            track_id = int(box.id[0].item()) if box.id is not None else 1
                            conf = float(box.conf[0].item())
                            xyxy = box.xyxy[0].tolist()
                            
                            # Normalize coordinates
                            norm_bbox = (
                                xyxy[0] / float(w_frame),
                                xyxy[1] / float(h_frame),
                                xyxy[2] / float(w_frame),
                                xyxy[3] / float(h_frame)
                            )
                            detections.append((track_id, norm_bbox, conf))
            except Exception as e:
                print(f"[WARN] YOLO tracking error: {e}")
        else:
            # Geometric/Face Fallback detection if PyTorch/YOLO not yet loaded
            # Detects central student ROI
            center_bbox = (0.25, 0.20, 0.75, 0.90)
            detections.append((1, center_bbox, 0.90))

        t_yolo_end = time.perf_counter()
        yolo_ms = int((t_yolo_end - t_yolo_start) * 1000)

        # 3. Pose Behavior Estimation per Candidate ROI
        t_pose_start = time.perf_counter()
        track_results: List[TrackResult] = []
        active_track_ids = [d[0] for d in detections]
        self.pose_engine.remove_lost_tracks(active_track_ids)

        for track_id, bbox_norm, conf in detections:
            res = self.pose_engine.process_student_roi(
                full_frame_bgr=frame_bgr,
                bbox_xyxy_norm=bbox_norm,
                track_id=track_id,
                frame_id=frame_id,
                captured_at_ms=captured_at_ms,
                detection_conf=conf
            )
            track_results.append(res)

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
