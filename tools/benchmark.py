"""
Measure the backend pipeline speed (ms per frame, FPS) on a video, fed like the web client
(960 px wide, 10 FPS, JPEG). Prints the total and the two helper models separately.

    python tools/benchmark.py --video D:/HTTM/test/classroom.mp4
    python tools/benchmark.py --video classroom.mp4 --frames 400
Compare modes with the environment variable AUX_MODEL_EVERY_N (1 = every model on every frame).
"""
import argparse
import base64
import os
import statistics
import sys
import time
from pathlib import Path

import cv2

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
os.chdir(REPO / "backend")
from app.config import settings  # noqa: E402
from app.inference.tracking_core import SessionInferencePipeline  # noqa: E402

WARMUP = 10


def timed(fn, bucket):
    def wrapper(*a, **k):
        import torch
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        t = time.perf_counter()
        out = fn(*a, **k)
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        bucket.append((time.perf_counter() - t) * 1000)
        return out
    return wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--frames", type=int, default=200)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    stride = max(1, round(fps / 10))
    jpgs, n = [], 0
    while len(jpgs) < args.frames + WARMUP:
        ok, frame = cap.read()
        if not ok:
            break
        if n % stride == 0:
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (960, round(960 * h / w)))
            jpgs.append((small.shape[1], small.shape[0],
                         base64.b64encode(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]).decode()))
        n += 1

    pipe = SessionInferencePipeline("benchmark")
    turn_ms, phone_ms = [], []
    if pipe.turn_classifier is not None:
        pipe.turn_classifier.predict = timed(pipe.turn_classifier.predict, turn_ms)
    if pipe.phone_detector is not None:
        pipe.phone_detector = timed(pipe.phone_detector, phone_ms)

    total = []
    for i, (w, h, jpg) in enumerate(jpgs):
        t = time.perf_counter()
        pipe.process_frame(i, i * 100, w, h, jpg)
        if i >= WARMUP:
            total.append((time.perf_counter() - t) * 1000)
    pipe.close()

    mean = lambda xs: statistics.mean(xs) if xs else 0.0
    ms = mean(total)
    print(f"AUX_MODEL_EVERY_N={settings.AUX_MODEL_EVERY_N}  frames={len(total)}")
    print(f"pipeline: {ms:.1f} ms/frame = {1000 / ms:.1f} FPS")
    print(f"turn_cls: {mean(turn_ms):.1f} ms x {len(turn_ms)} calls · phone: {mean(phone_ms):.1f} ms x {len(phone_ms)} calls")


if __name__ == "__main__":
    main()
