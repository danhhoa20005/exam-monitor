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

PHONE_CLASS_ID = 67   # COCO 'cell phone'


def phone_near_wrists(kpts, phone_boxes_px, max_sw: float = None) -> bool:
    """True if a detected phone's centre lies within max_sw shoulder widths of a visible wrist."""
    if kpts is None or len(kpts) < 11 or not phone_boxes_px:
        return False
    max_sw = settings.PHONE_NEAR_WRIST_SW if max_sw is None else max_sw
    shoulder_w = max(10.0, abs(float(kpts[5][0]) - float(kpts[6][0])))
    wrists = [w for w in (kpts[9], kpts[10]) if len(w) < 3 or float(w[2]) >= 0.3]
    for x1, y1, x2, y2 in phone_boxes_px:
        bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
        # a held phone is small and elongated; a pen-holding fist is bigger and squarer
        if bw * bh > settings.PHONE_MAX_AREA_SW2 * shoulder_w ** 2 or max(bw, bh) / min(bw, bh) < settings.PHONE_MIN_ASPECT:
            continue
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        for w in wrists:
            if ((cx - float(w[0])) ** 2 + (cy - float(w[1])) ** 2) ** 0.5 <= max_sw * shoulder_w:
                return True
    return False


class SessionInferencePipeline:
    """End-to-end inference pipeline for a single active monitoring session."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.pose_engine = PoseBehaviorEngine()
        self.event_manager = EventManager(session_id)
        self.yolo_model = None
        self.is_pose_model = False
        self.is_custom_student_model = False
        self.source_id: Optional[str] = None
        self._init_yolo()
        self.turn_classifier = None
        if self.is_pose_model and os.path.exists(settings.TURN_CLS_MODEL_PATH):
            try:
                from app.inference.turn_classifier import TurnClassifier
                self.turn_classifier = TurnClassifier(str(settings.TURN_CLS_MODEL_PATH))
                print(f"[OK] Turn classifier loaded: {settings.TURN_CLS_MODEL_PATH}")
            except Exception as e:
                print(f"[WARN] Failed to load turn classifier: {e}")
        self.phone_detector = None
        if self.is_pose_model and settings.PHONE_MODEL_PATH.name.lower() != "none.pt":
            try:
                if not os.path.exists(settings.PHONE_MODEL_PATH):
                    from models.download_models import download_yolo_pose_model
                    download_yolo_pose_model(settings.PHONE_MODEL_PATH.name)
                from ultralytics import YOLO
                self.phone_detector = YOLO(str(settings.PHONE_MODEL_PATH))
                print(f"[OK] Phone detector loaded: {settings.PHONE_MODEL_PATH}")
            except Exception as e:
                print(f"[WARN] Failed to load phone detector: {e}")

    def _init_yolo(self):
        """Initialize YOLO11-Pose detector (from dyingangell/Cheating-detection-YOLO) or custom weights."""
        pose_model_path = str(settings.YOLO_POSE_MODEL_PATH)
        custom_model_path = str(settings.YOLO_MODEL_PATH)
        fallback_path = str(settings.FALLBACK_YOLO_PATH)

        # Behaviour analysis needs keypoints, so the pose model must win over any detect-only weights.
        if not os.path.exists(pose_model_path):
            print(f"[INFO] Downloading YOLO11-Pose weights to {pose_model_path}...")
            try:
                from models.download_models import download_yolo_pose_model
                download_yolo_pose_model(settings.YOLO_POSE_MODEL_PATH.name)
            except Exception as dl_err:
                print(f"[WARN] Could not auto-download pose model: {dl_err}")

        target_path = None
        if os.path.exists(pose_model_path):
            target_path = pose_model_path
            self.is_pose_model = True
            print(f"[OK] Loading YOLO11-Pose model: {pose_model_path}")
        elif os.path.exists(custom_model_path):
            target_path = custom_model_path
            self.is_custom_student_model = True
            print(f"[WARN] Pose model unavailable, using detect-only weights {custom_model_path}: "
                  f"every track will be POSE_UNAVAILABLE (no behaviour analysis)")
        elif os.path.exists(fallback_path):
            target_path = fallback_path
            print(f"[WARN] Pose model unavailable, using detect-only fallback {fallback_path}")

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
        jpeg_base64: str,
        source_id: Optional[str] = None
    ) -> FrameResult:
        """
        Decode JPEG, run YOLO-Pose detection, track candidates, analyze posture, and update events.
        source_id: changes whenever the client switches camera or loads another video.
        """
        t0 = time.perf_counter()

        if source_id is not None and source_id != self.source_id:
            self.reset_tracking(captured_at_ms)
            self.source_id = source_id

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
                    conf=settings.YOLO_CONF,
                    imgsz=settings.YOLO_IMGSZ
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

        turn_probs = [None] * len(detections)
        if self.turn_classifier is not None and detections:
            try:
                boxes_px = [(b[0] * w_frame, b[1] * h_frame, b[2] * w_frame, b[3] * h_frame) for _, b, _, _, _ in detections]
                turn_probs = self.turn_classifier.predict(frame_bgr, boxes_px)
            except Exception as e:
                print(f"[WARN] Turn classifier error: {e}")

        phone_boxes = None
        if self.phone_detector is not None and detections:
            try:
                r = self.phone_detector(frame_bgr, imgsz=settings.YOLO_IMGSZ, conf=settings.PHONE_CONF,
                                        classes=[PHONE_CLASS_ID], verbose=False)[0]
                phone_boxes = r.boxes.xyxy.tolist()
            except Exception as e:
                print(f"[WARN] Phone detector error: {e}")

        for (track_id, bbox_norm, conf, act_name, kpts), turn_prob in zip(detections, turn_probs):
            phone_seen = phone_near_wrists(kpts, phone_boxes) if phone_boxes is not None else None
            try:
                res = self.pose_engine.process_student_roi(
                    full_frame_bgr=frame_bgr,
                    bbox_xyxy_norm=bbox_norm,
                    track_id=track_id,
                    frame_id=frame_id,
                    captured_at_ms=captured_at_ms,
                    detection_conf=conf,
                    person_kpts=kpts,
                    activity=act_name if act_name in ["attentive", "hand_raised", "inattentive"] else "attentive",
                    turn_prob=turn_prob,
                    phone_seen=phone_seen
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

    def reset_tracking(self, now_ms: int):
        """
        Forget every track, track ID and per-student baseline. Without this, a new video is
        matched onto the previous source's tracks (same seats -> same boxes) and inherits
        their baselines, which inverts the result when that baseline was a turned head.
        """
        self.event_manager.close_all_on_stop(now_ms)
        self.pose_engine.reset_session()
        predictor = getattr(self.yolo_model, "predictor", None) if self.yolo_model is not None else None
        for tracker in getattr(predictor, "trackers", None) or []:
            tracker.reset()

    def close(self):
        """Release session resources."""
        now_ms = int(time.time() * 1000)
        self.event_manager.close_all_on_stop(now_ms)
        self.pose_engine.reset_session()
