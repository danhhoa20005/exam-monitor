"""
Trích frame từ video phòng thi để nhóm gán nhãn bổ sung (BowHead / TurnHead).

Cách dùng:
    python extract_frames.py <TRAINING_WORKDIR>/test/classroom.mp4 [video2.mp4 ...] --every 1.5

Kết quả: <TRAINING_WORKDIR>/dataset/_to_label/<ten_video>/*.jpg
Gán nhãn bằng CVAT / Roboflow / LabelImg theo đúng 2 lớp, thứ tự:
    0 = BowHead, 1 = TurnHead
Export định dạng YOLO rồi đặt vào:
    <TRAINING_WORKDIR>/dataset/_labeled_exam/<ten_video>/images/*.jpg
    <TRAINING_WORKDIR>/dataset/_labeled_exam/<ten_video>/labels/*.txt
và chạy lại prepare_behavior_dataset.py (mỗi video tự thành 1 nguồn, không bị rò rỉ).
"""
import argparse
import os

import cv2

from training_paths import DATASET_DIR

OUT_ROOT = f"{DATASET_DIR}/_to_label"


def extract(video_path, every_s):
    name = os.path.splitext(os.path.basename(video_path))[0]
    out_dir = os.path.join(OUT_ROOT, name)
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(round(fps * every_s)))
    idx = saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            # giữ nguyên độ phân giải gốc
            cv2.imwrite(os.path.join(out_dir, f"{name}_{idx:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            saved += 1
        idx += 1
    cap.release()
    print(f"{video_path}: {saved} frame -> {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--every", type=float, default=1.5, help="khoảng cách giữa 2 frame (giây)")
    args = ap.parse_args()
    for v in args.videos:
        extract(v, args.every)
