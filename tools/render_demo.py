"""
Render a demo video (B1) from the real backend pipeline: each scene is fed to SessionInferencePipeline at
10 FPS / 960 px exactly like the web client, and the result is drawn on every source frame:
    green = normal, orange = observing, red = REVIEW (+ seat number, risk score, reason),
    a red banner for every new alert, and a title card per scene.

Usage (from the repo root, backend venv):
    python tools/render_demo.py --out demo.mp4
    python tools/render_demo.py --scene "D:/x.mp4|Tiêu đề|0|30" --scene ...   # own scenes: path|title|start_s|end_s
Default scenes need TRAINING_WORKDIR (DS-03 videos + test/classroom.mp4), see training/README.md.
"""
import argparse
import base64
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
os.chdir(REPO / "backend")   # model paths in the backend config are relative to backend/
from app.inference.tracking_core import SessionInferencePipeline  # noqa: E402

WORK = Path(os.environ.get("TRAINING_WORKDIR", REPO / "training" / "workspace"))
DS03 = WORK / "dataset" / "_raw" / "ds03"
DEFAULT_SCENES = [
    (DS03 / "v_c5_s5_s6.MOV", "1. Làm bài bình thường: không cảnh báo", 0, 99),
    (DS03 / "v_c3_s5.MOV", "2. Quay đầu nhìn bài bạn", 0, 99),
    (DS03 / "v_c1_s5_s6.MOV", "3. Dùng điện thoại", 0, 99),
    (WORK / "test" / "classroom.mp4", "4. Camera toàn cảnh lớp học đông người", 37, 63),
]
OUT_W, OUT_H, OUT_FPS = 1280, 720, 25
PROC_FPS, PROC_W = 10, 960          # what the web client sends
REASON_VI = {"TURNING": "Quay đầu", "PHONE": "Điện thoại", "UNDER_DESK": "Cúi dưới bàn", "BENDING": "Cúi người"}
GREEN, ORANGE, RED = (60, 200, 90), (0, 165, 255), (40, 40, 230)   # BGR

FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(str(FONT_DIR / name) if (FONT_DIR / name).exists() else name, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_SMALL, F_MED, F_BIG, F_TITLE = font(18, True), font(24, True), font(30, True), font(46, True)


def draw_texts(img, items):
    """items: (xy, text, font, rgb, bg_rgba or None). PIL so Vietnamese diacritics render."""
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).convert("RGBA")
    layer = Image.new("RGBA", pil.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (x, y), text, fnt, rgb, bg in items:
        if bg:
            l, t, r, b = d.textbbox((x, y), text, font=fnt)
            d.rectangle((l - 6, t - 4, r + 6, b + 4), fill=bg)
        d.text((x, y), text, font=fnt, fill=rgb)
    return cv2.cvtColor(np.array(Image.alpha_composite(pil, layer).convert("RGB")), cv2.COLOR_RGB2BGR)


def fit(frame):
    h, w = frame.shape[:2]
    s = min(OUT_W / w, OUT_H / h)
    small = cv2.resize(frame, (round(w * s), round(h * s)))
    canvas = np.zeros((OUT_H, OUT_W, 3), np.uint8)
    y0, x0 = (OUT_H - small.shape[0]) // 2, (OUT_W - small.shape[1]) // 2
    canvas[y0:y0 + small.shape[0], x0:x0 + small.shape[1]] = small
    return canvas, (x0, y0, small.shape[1], small.shape[0])


def card(lines, sub=""):
    img = np.full((OUT_H, OUT_W, 3), (40, 26, 15), np.uint8)
    items = [((80, 260 + 70 * i), t, F_TITLE, (255, 255, 255), None) for i, t in enumerate(lines)]
    if sub:
        items.append(((80, 280 + 70 * len(lines)), sub, F_MED, (170, 190, 210), None))
    return draw_texts(img, items)


def overlay(frame, tracks, title, alerts, t_s):
    img, (x0, y0, w, h) = fit(frame)
    crowded = len(tracks) > 6
    texts = []
    for t in tracks:
        x1, y1, x2, y2 = t.bbox_xyxy_norm
        p1 = (int(x0 + x1 * w), int(y0 + y1 * h))
        p2 = (int(x0 + x2 * w), int(y0 + y2 * h))
        color = RED if t.status == "REVIEW" else ORANGE if t.status == "OBSERVING" else GREEN
        cv2.rectangle(img, p1, p2, color, 3 if t.status == "REVIEW" else 2)
        seat = f"Ghế {t.seat_id:02d}" if t.seat_id else f"ID {t.track_id}"
        if t.status in ("REVIEW", "OBSERVING") or not crowded:
            reasons = ", ".join(REASON_VI.get(r, r) for r in t.reasons)
            label = f"{seat} · {t.suspicion_score or 0}" + (f" · {reasons}" if reasons else "")
            if t.status == "CALIBRATING":
                label = f"{seat} · lấy mốc"
            bg = {"REVIEW": (230, 40, 40, 230), "OBSERVING": (255, 150, 0, 220)}.get(t.status, (40, 150, 70, 200))
            texts.append(((p1[0], max(44, p1[1] - 28)), label, F_SMALL, (255, 255, 255), bg))
    n_review = sum(t.status == "REVIEW" for t in tracks)
    texts.append(((16, 10), title, F_MED, (255, 255, 255), (15, 26, 40, 210)))
    status = f"{len(tracks)} thí sinh · {n_review} cần xem lại · {t_s:5.1f}s"
    texts.append(((OUT_W - 360, 12), status, F_SMALL, (255, 255, 255), (15, 26, 40, 210)))
    latest = list(dict.fromkeys(text for _, text in reversed(alerts)))[:2]   # newest first, one per seat/reason
    for i, text in enumerate(latest):
        texts.append(((16, OUT_H - 52 - 44 * i), f"CẢNH BÁO MỚI: {text}  →  đã lưu clip bằng chứng", F_MED,
                      (255, 255, 255), (220, 30, 30, 235)))
    if alerts:
        cv2.rectangle(img, (0, 0), (OUT_W - 1, OUT_H - 1), RED, 6)
    return draw_texts(img, texts)


def render_scene(writer, path, title, start_s, end_s):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    stride = max(1, round(fps / PROC_FPS))
    pipe = SessionInferencePipeline(f"demo-{Path(path).stem}")
    tracks, in_review, alerts, n, written = [], set(), [], 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t_s = n / fps
        if t_s > end_s:
            break
        if n % stride == 0:
            hh, ww = frame.shape[:2]
            small = cv2.resize(frame, (PROC_W, round(PROC_W * hh / ww)))
            jpg = base64.b64encode(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])[1]).decode()
            res = pipe.process_frame(n, int(t_s * 1000), small.shape[1], small.shape[0], jpg)
            tracks = res.tracks
            for t in tracks:
                if t.status == "REVIEW" and t.track_id not in in_review:
                    in_review.add(t.track_id)
                    seat = f"Ghế {t.seat_id:02d}" if t.seat_id else f"ID {t.track_id}"
                    alerts.append((t_s, f"{seat} — " + ", ".join(REASON_VI.get(r, r) for r in t.reasons)))
                    print(f"  {t_s:5.1f}s REVIEW {alerts[-1][1]}")
                elif t.status != "REVIEW":
                    in_review.discard(t.track_id)
        alerts = [a for a in alerts if t_s - a[0] < 2.5]   # banner stays 2.5 s
        if t_s >= start_s:
            out = overlay(frame, tracks, title, alerts, t_s)
            while written < (t_s - start_s) * OUT_FPS:   # resample source fps to OUT_FPS
                writer.write(out)
                written += 1
        n += 1
    cap.release()
    pipe.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(WORK / "result" / "demo" / "demo.mp4"))
    ap.add_argument("--scene", action="append", help="path|title|start_s|end_s")
    args = ap.parse_args()
    scenes = [(p, t, float(a), float(b)) for p, t, a, b in (s.split("|") for s in args.scene)] if args.scene \
        else DEFAULT_SCENES
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"avc1"), OUT_FPS, (OUT_W, OUT_H))
    if not writer.isOpened():
        writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), OUT_FPS, (OUT_W, OUT_H))
    intro = card(["Giám sát gian lận phòng thi bằng camera"],
                 "YOLO11-Pose + turn_cls (nhóm train) + YOLO11m · xanh = bình thường, cam = theo dõi, đỏ = cần xem lại")
    for _ in range(OUT_FPS * 3):
        writer.write(intro)
    for path, title, a, b in scenes:
        print(f"[scene] {title}")
        c = card([title], "2 giây đầu: hệ thống lấy mốc tư thế riêng của từng thí sinh")
        for _ in range(int(OUT_FPS * 1.5)):
            writer.write(c)
        render_scene(writer, path, title, a, b)
    writer.release()
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
