"""
detect_cheating.py - Real-Time Cheating Detection using YOLO11-Pose
(Direct desktop/standalone runner from dyingangell/Cheating-detection-YOLO).

Features:
- Real-time YOLO11-Pose keypoints extraction (Nose, Shoulders, Wrists)
- Individual student auto-calibration baseline circle
- Lateral head turn vs depth paper-writing deviation
- Hazard meter (0-100%) and CHEATING / REVIEW alert overlay
- Bounding boxes, skeletal bones, and telemetry HUD

Usage:
    Webcam:  python tools/detect_cheating.py
    Video:   python tools/detect_cheating.py --source path/to/video.mp4
    Model:   python tools/detect_cheating.py --model backend/models/yolo11n-pose.pt
"""

import os
import sys
import time
import math
import argparse
from datetime import datetime
import cv2
import numpy as np
from ultralytics import YOLO

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.inference.pose_behavior import PoseBehaviorEngine

def parse_args():
    parser = argparse.ArgumentParser(description="Real-Time Exam Cheating Detection with YOLO11-Pose")
    parser.add_argument("--source", type=str, default="0",
                        help="Video source: 0=webcam, or video file path")
    parser.add_argument("--model", type=str, default="backend/models/yolo11n-pose.pt",
                        help="YOLO11-Pose model weights path (e.g. yolo11n-pose.pt, yolo11s-pose.pt, yolo11l-pose.pt)")
    parser.add_argument("--conf", type=float, default=0.30,
                        help="Detection confidence threshold (default 0.30)")
    parser.add_argument("--device", type=str, default="cpu",
                        help="Compute device: cpu, mps, or cuda")
    return parser.parse_args()

def draw_pose_hud(frame, results, engine: PoseBehaviorEngine, frame_id: int, captured_at_ms: int):
    h, w = frame.shape[:2]
    if not results or len(results) == 0:
        return frame

    res = results[0]
    boxes = res.boxes
    if boxes is None or len(boxes) == 0:
        return frame

    has_kpts = res.keypoints is not None and hasattr(res.keypoints, 'data') and res.keypoints.data is not None

    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        track_id = int(box.id[0].item()) if box.id is not None else (i + 1)

        norm_bbox = (x1 / float(w), y1 / float(h), x2 / float(w), y2 / float(h))
        kpts = res.keypoints.data[i].cpu().numpy() if has_kpts and len(res.keypoints.data) > i else None

        # Evaluate cheating behavior through the engine
        track_res = engine.process_student_roi(
            full_frame_bgr=frame,
            bbox_xyxy_norm=norm_bbox,
            track_id=track_id,
            frame_id=frame_id,
            captured_at_ms=captured_at_ms,
            detection_conf=conf,
            person_kpts=kpts
        )

        state = engine.get_or_create_state(track_id)

        # Color based on status
        if track_res.status == "REVIEW":
            color = (0, 0, 255)       # Red
            status_text = "CHEATING ALERT!"
        elif track_res.status == "OBSERVING":
            color = (0, 165, 255)     # Amber/Orange
            status_text = "OBSERVING"
        elif track_res.status == "CALIBRATING":
            color = (255, 200, 0)     # Cyan/Blue
            status_text = f"CALIBRATING ({track_res.calibration_samples}/20)"
        else:
            color = (0, 220, 0)       # Green
            status_text = "NORMAL"

        # 1. Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # 2. Keypoints visualization (skeleton bones)
        if kpts is not None and len(kpts) >= 7:
            for pt in kpts[:11]:
                px, py, pc = int(pt[0]), int(pt[1]), float(pt[2]) if len(pt) > 2 else 1.0
                if pc >= 0.3:
                    cv2.circle(frame, (px, py), 4, (0, 255, 255), -1)

            # Draw shoulder line
            if float(kpts[5][2]) >= 0.3 and float(kpts[6][2]) >= 0.3:
                cv2.line(frame, (int(kpts[5][0]), int(kpts[5][1])), (int(kpts[6][0]), int(kpts[6][1])), (255, 255, 0), 2)

            # Draw baseline circle & deviation line if calibrated
            if state.is_calibrated and state.base_nose_x is not None:
                shoulder_w = abs(float(kpts[6][0]) - float(kpts[5][0]))
                mid_x = (float(kpts[5][0]) + float(kpts[6][0])) / 2.0
                mid_y = (float(kpts[5][1]) + float(kpts[6][1])) / 2.0
                base_px = int(mid_x + state.base_nose_x * shoulder_w)
                base_py = int(mid_y + state.base_nose_y * shoulder_w)
                base_radius_px = int(0.38 * shoulder_w)
                cv2.circle(frame, (base_px, base_py), base_radius_px, (200, 200, 200), 1)
                cv2.circle(frame, (base_px, base_py), 3, (0, 255, 0), -1)
                # Line from nose to baseline
                nx, ny = int(kpts[0][0]), int(kpts[0][1])
                cv2.line(frame, (nx, ny), (base_px, base_py), color, 1)

        # 3. Label HUD
        label = f"ID:{track_id} | {status_text} | Score: {track_res.suspicion_score}%"
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(frame, (x1, max(0, y1 - label_size[1] - 8)), (x1 + label_size[0] + 6, y1), color, -1)
        cv2.putText(frame, label, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # 4. Telemetry details below box
        telemetry = f"Yaw: {track_res.yaw_delta_deg:+.1f} deg | Bend: {track_res.nose_drop_ratio:.2f}"
        if track_res.reasons:
            telemetry += f" | {', '.join(track_res.reasons)}"
        cv2.putText(frame, telemetry, (x1, min(h - 5, y2 + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    return frame

def main():
    args = parse_args()
    print("=" * 65)
    print("🎯 Real-Time Cheating Detection with YOLO11-Pose (dyingangell)")
    print(f"📦 Model:  {args.model}")
    print(f"📹 Source: {args.source}")
    print("=" * 65)

    if not os.path.exists(args.model):
        print(f"[INFO] Model not found at {args.model}. Auto-downloading...")
        YOLO(os.path.basename(args.model))
        if os.path.exists(os.path.basename(args.model)):
            os.rename(os.path.basename(args.model), args.model)

    print(f"[OK] Loading YOLO11-Pose: {args.model}...")
    model = YOLO(args.model)
    engine = PoseBehaviorEngine()

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video source: {args.source}")
        return

    print("✅ Video stream opened successfully.")
    print("👉 Press 'q' in the window to exit.")

    frame_id = 0
    t_prev = time.time()
    fps = 30.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] Video stream ended or camera disconnected.")
                break

            frame_id += 1
            now_ms = int(time.time() * 1000)

            # Run YOLO11-Pose tracking
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=args.conf,
                verbose=False
            )

            # Draw Cheating Detection Overlay
            frame = draw_pose_hud(frame, results, engine, frame_id, now_ms)

            # Calculate FPS
            t_curr = time.time()
            dt = t_curr - t_prev
            t_prev = t_curr
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            # Overlay FPS banner
            cv2.rectangle(frame, (0, 0), (220, 36), (0, 0, 0), -1)
            cv2.putText(frame, f"FPS: {fps:.1f} | YOLO11-Pose", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            cv2.imshow("Exam Cheating Detection - YOLO11-Pose HUD", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n[OK] Monitor session closed cleanly.")

if __name__ == "__main__":
    main()
