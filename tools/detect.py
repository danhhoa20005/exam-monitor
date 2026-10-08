"""
detect.py - Real-Time Classroom & Exam Student Activity Detection
Captures webcam/video frames, runs YOLOv8 inference,
draws bounding boxes with labels, shows FPS, logs to CSV.

Usage:
    Webcam:  python tools/detect.py
    Video:   python tools/detect.py --source video.mp4
"""

import cv2
import csv
import time
import os
import argparse
from datetime import datetime
from ultralytics import YOLO


def resolve_model_path(user_model_path=None):
    if user_model_path and os.path.exists(user_model_path):
        return user_model_path

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    
    candidates = [
        user_model_path,
        os.path.join(project_root, "backend", "models", "best.pt"),
        os.path.join(project_root, "backend", "models", "yolo11n-pose.pt"),
        os.path.join(project_root, "backend", "models", "yolo11s-pose.pt"),
        os.path.join(project_root, "backend", "models", "yolo11l-pose.pt"),
        "backend/models/best.pt",
        "backend/models/yolo11n-pose.pt",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return user_model_path or "backend/models/best.pt"


def parse_args():
    parser = argparse.ArgumentParser(description="Classroom & Exam Activity Detection")
    parser.add_argument("--source", type=str, default="0",
                        help="Video source: 0=webcam, or video file path")
    parser.add_argument("--model", type=str, default=None,
                        help="YOLO model weights path")
    parser.add_argument("--conf", type=float, default=0.45,
                        help="Confidence threshold (0.0-1.0)")
    return parser.parse_args()


def setup_csv(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(log_dir, f"session_{timestamp}.csv")
    csv_file = open(csv_path, mode="w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow(["timestamp", "class_name", "confidence", "x1", "y1", "x2", "y2"])
    print(f"Logging detections to: {csv_path}")
    return csv_file, writer, csv_path


def draw_detections(frame, results, writer):
    colors = {
        "attentive": (0, 200, 0),       # Green
        "hand_raised": (255, 150, 0),    # Blue
        "inattentive": (0, 0, 255),      # Red
    }

    detections = {"attentive": 0, "hand_raised": 0, "inattentive": 0}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = result.names[cls_id]

            if cls_name in detections:
                detections[cls_name] += 1

            color = colors.get(cls_name, (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            label = f"{cls_name} {conf:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(frame, (x1, max(0, y1 - label_size[1] - 10)),
                          (x1 + label_size[0], y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            writer.writerow([now, cls_name, f"{conf:.3f}", x1, y1, x2, y2])

    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, h - 40), (w, h), (0, 0, 0), -1)
    summary = f"Attentive: {detections['attentive']}  |  "
    summary += f"Hand Raised: {detections['hand_raised']}  |  "
    summary += f"Inattentive: {detections['inattentive']}"
    cv2.putText(frame, summary, (10, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return frame


def main():
    args = parse_args()
    model_path = resolve_model_path(args.model)
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    print("Model loaded successfully!")

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"ERROR: Cannot open video source: {args.source}")
        return

    print(f"Video source opened: {args.source}")
    print("Press 'q' in window to quit")

    csv_file, writer, csv_path = setup_csv()

    prev_time = time.time()
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Video ended or camera disconnected")
                break

            results = model.predict(frame, conf=args.conf, verbose=False)
            frame = draw_detections(frame, results, writer)

            frame_count += 1
            curr_time = time.time()
            if curr_time - prev_time >= 1.0:
                fps = frame_count / (curr_time - prev_time)
                frame_count = 0
                prev_time = curr_time
            else:
                fps = 30.0

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            cv2.imshow("Classroom & Exam Activity Monitor", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        csv_file.close()
        print(f"\nSession ended! Log saved to: {csv_path}")


if __name__ == "__main__":
    main()
