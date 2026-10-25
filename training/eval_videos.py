"""
Đánh giá HỆ THỐNG (backend exam-monitor) trên bộ video có nhãn theo từng video.

Mỗi video chạy đúng pipeline backend (YOLO11-Pose + ByteTrack + luật tư thế [+ model turn_cls])
ở 10 FPS, khung 960 px như web gửi lên, với 2 cấu hình:
    rules : chỉ luật tư thế
    ai    : luật tư thế + model phân loại quay đầu của nhóm (turn_cls.pt)
Một video được coi là "bị báo" nếu có ít nhất 1 lần REVIEW.

Chạy:
    python eval_videos.py                       # mặc định: bộ DS-03
    python eval_videos.py --videos thu_muc_video --labels nhan.csv

Kết quả: <TRAINING_WORKDIR>/result/eval/<ten>.csv + ảnh tại thời điểm REVIEW để kiểm tra bằng mắt.
"""
import argparse
import base64
import csv
import os
import re
import sys
import time
from collections import defaultdict

import cv2

from training_paths import BACKEND_DIR, DATASET_DIR, RESULT_DIR

BACKEND = str(BACKEND_DIR)
sys.path.insert(0, BACKEND)
from app.config import settings                                   # noqa: E402
from app.inference.tracking_core import SessionInferencePipeline  # noqa: E402

TARGET_FPS = 10
TARGET_W = 960

# DS-03 (Hashemite University): mã lớp trong tên file v_c<k>_s<i>[_s<j>]...
# Thứ tự trong README KHÔNG khớp tên file; ánh xạ dưới đây xác nhận bằng cách xem frame.
DS03_CLASSES = {
    "c1": "phone",              # dùng điện thoại
    "c2": "exchange_paper",     # đổi bài thi (cả hai người)
    "c3": "look_at_paper",      # nhìn bài bạn  -> hệ thống PHẢI báo
    "c4": "cheat_sheet",        # dùng phao
    "c5": "not_cheating",       # không gian lận (cả hai người) -> KHÔNG được báo
}


def ds03_people(filename):
    """
    Mỗi video có 2 người: trái và phải. Sinh viên số lẻ ngồi trái, số chẵn ngồi phải.
    Trả về {"left": nhãn, "right": nhãn}; người không được nêu tên trong file = not_cheating.
    """
    m = re.match(r"v_(c\d)_((?:s\d_?)+)", filename)
    if not m:
        return {}
    act = DS03_CLASSES[m.group(1)]
    subjects = [int(s) for s in re.findall(r"s(\d)", m.group(2))]
    people = {"left": "not_cheating", "right": "not_cheating"}
    for s in subjects:
        people["left" if s % 2 else "right"] = act
    return people


def ds03_split(filename):
    """dev = sinh viên 1-4 (dùng để chỉnh thông số), test = sinh viên 5-8 (chỉ để chấm điểm cuối)."""
    subjects = [int(s) for s in re.findall(r"_s(\d)", filename)]
    return "dev" if subjects and max(subjects) <= 4 else "test"


def run_video(path, use_ai, snap_dir):
    settings.TURN_CLS_MODEL_PATH = settings.MODELS_DIR / ("turn_cls.pt" if use_ai else "__disabled__.pt")
    pipe = SessionInferencePipeline(f"eval-{os.path.basename(path)}")
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    stride = max(1, round(fps / TARGET_FPS))
    in_review, onsets, max_score, n, t0 = set(), [], 0, 0, time.perf_counter()
    flagged_sides = set()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if n % stride == 0:
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (TARGET_W, round(TARGET_W * h / w)))
            jpg = base64.b64encode(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])[1]).decode()
            r = pipe.process_frame(n, int(n * 1000 / fps), small.shape[1], small.shape[0], jpg)
            for t in r.tracks:
                max_score = max(max_score, t.suspicion_score or 0)
                if t.status == "REVIEW" and t.track_id not in in_review:
                    in_review.add(t.track_id)
                    side = "left" if (t.bbox_xyxy_norm[0] + t.bbox_xyxy_norm[2]) / 2 < 0.5 else "right"
                    flagged_sides.add(side)
                    onsets.append((round(n / fps, 1), t.track_id, side))
                    if snap_dir:
                        x1, y1, x2, y2 = (int(v * s) for v, s in zip(t.bbox_xyxy_norm, (TARGET_W, small.shape[0]) * 2))
                        cv2.rectangle(small, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(small, f"t={n / fps:.1f}s #{t.track_id} ai={t.ai_turn_prob}", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        cv2.imwrite(os.path.join(snap_dir, f"{os.path.splitext(os.path.basename(path))[0]}"
                                                           f"_{'ai' if use_ai else 'rules'}_{n}.jpg"), small)
                elif t.status != "REVIEW":
                    in_review.discard(t.track_id)
        n += 1
    cap.release()
    pipe.close()
    return {"left_flagged": int("left" in flagged_sides), "right_flagged": int("right" in flagged_sides),
            "n_review": len(onsets), "max_score": max_score,
            "onsets": " ".join(f"{s}s#{i}{side[0].upper()}" for s, i, side in onsets),
            "duration_s": round(n / fps, 1), "proc_s": round(time.perf_counter() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", default=f"{DATASET_DIR}/_raw/ds03")
    ap.add_argument("--labels", help="CSV: filename,label (mặc định suy ra từ tên file DS-03)")
    ap.add_argument("--name", default="ds03")
    ap.add_argument("--modes", default="rules,ai", help="cấu hình cần chạy, vd: ai")
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
    args = ap.parse_args()
    modes = args.modes.split(",")

    labels = {}
    if args.labels:
        # CSV: filename,left,right  (nhãn hành vi của người ngồi trái / phải)
        with open(args.labels, encoding="utf-8") as fh:
            labels = {row["filename"]: {"left": row["left"], "right": row["right"]} for row in csv.DictReader(fh)}
    files = sorted(f for f in os.listdir(args.videos) if f.lower().endswith((".mov", ".mp4", ".avi", ".mkv")))
    if args.split != "all":
        files = [f for f in files if ds03_split(f) == args.split]

    out_dir = f"{RESULT_DIR}/eval"
    snap_dir = os.path.join(out_dir, f"{args.name}_snaps")
    os.makedirs(snap_dir, exist_ok=True)
    rows = []
    for i, f in enumerate(files, 1):
        people = labels.get(f) or ds03_people(f)
        for mode in modes:
            res = run_video(os.path.join(args.videos, f), mode == "ai", snap_dir)
            rows.append({"file": f, "split": ds03_split(f), "left": people.get("left"), "right": people.get("right"),
                         "mode": mode, **res})
            print(f"[{i}/{len(files)}] {f:20s} L={people.get('left'):14s} R={people.get('right'):14s} {mode:5s} "
                  f"flag L={res['left_flagged']} R={res['right_flagged']} max={res['max_score']:3d} {res['onsets']}")

    csv_path = os.path.join(out_dir, f"{args.name}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

    summarize(rows, modes)
    print(f"\nChi tiết: {csv_path}\nẢnh lúc báo: {snap_dir}")


def summarize(rows, modes):
    """Mỗi (video, người) là 1 mẫu: người gian lận phải bị báo, người bình thường không được báo."""
    for split in sorted({r["split"] for r in rows}) + ["all"]:
        sub = [r for r in rows if split == "all" or r["split"] == split]
        agg = defaultdict(lambda: [0, 0])
        for r in sub:
            for side in ("left", "right"):
                agg[(r[side], r["mode"])][0] += int(r[f"{side}_flagged"])
                agg[(r[side], r["mode"])][1] += 1
        print(f"\n===== [{split}] TỈ LỆ NGƯỜI BỊ BÁO (REVIEW) THEO HÀNH VI THẬT =====")
        print(f"{'Hành vi thật':16s} " + " ".join(f"{m:>10s}" for m in modes))
        for label in sorted({k[0] for k in agg}):
            print(f"{label:16s} " + " ".join(f"{agg[(label, m)][0]}/{agg[(label, m)][1]:<4d}".rjust(10) for m in modes))
        for mode in modes:
            cheat = [l for l in {k[0] for k in agg} if l != "not_cheating"]
            tp = sum(agg[(l, mode)][0] for l in cheat)
            pos = sum(agg[(l, mode)][1] for l in cheat)
            fp = agg[("not_cheating", mode)][0]
            ltp, lpos = agg[("look_at_paper", mode)]
            p_all = tp / max(1, tp + fp)
            print(f"[{split}/{mode}] nhìn bài bạn: Recall={ltp}/{lpos} | mọi hành vi gian lận: Recall={tp}/{pos} "
                  f"| báo nhầm={fp}/{agg[('not_cheating', mode)][1]} | Precision={p_all:.2f}")


if __name__ == "__main__":
    main()
