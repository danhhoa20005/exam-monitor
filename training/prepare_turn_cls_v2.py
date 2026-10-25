"""
Dataset turn_cls v2 = SCB (turn_cls v1) + ảnh cắt từ video thi thật DS-03.

DS-03 chia theo SINH VIÊN để không rò rỉ:  sv 1-3 -> train, sv 4 -> val, sv 5-8 -> test.
Nhãn cho từng khung (mặt DS-03 đủ lớn nên hình học khuôn mặt rất tin cậy):
  - người không gian lận (mọi video)            -> normal, nếu đầu gần mốc
  - người "nhìn bài bạn" (c3)                    -> turn nếu tai xa bị che + mũi lệch giữa hai mắt,
                                                    hoặc mũi lệch ngang >= 0.2 vai so với trung vị của video;
                                                    normal nếu đầu gần mốc; khung lưng chừng bị bỏ
  - các hành vi gian lận khác (điện thoại, phao, đổi bài) -> bỏ (không phải bài toán quay đầu)
Train/val có thêm bản thu nhỏ rồi phóng to lại (mặt ~30-60 px như camera CCTV toàn cảnh).

Kết quả: <TRAINING_WORKDIR>/dataset/turn_cls_v2/{train,val,test}/{normal,turn}
"""
import os
import random
import re
import shutil

import cv2
import numpy as np
from ultralytics import YOLO

from prepare_turn_cls import crop_person

from training_paths import DATASET_DIR, POSE_MODEL

V1 = f"{DATASET_DIR}/turn_cls"
DS03 = f"{DATASET_DIR}/_raw/ds03"
OUT = f"{DATASET_DIR}/turn_cls_v2"
POSE_MODEL = str(POSE_MODEL)
CLASSES = {"c1": "phone", "c2": "exchange", "c3": "look", "c4": "sheet", "c5": "normal"}
SEED = 42


def subject_split(s):
    return "train" if s <= 3 else "val" if s == 4 else "test"


def face_signals(k):
    """(rel_nose_x, profile_turn) từ keypoint COCO."""
    sw = abs(k[5][0] - k[6][0])
    if min(k[0][2], k[5][2], k[6][2]) < 0.3 or sw < 10:
        return None, False
    rel = (k[0][0] - (k[5][0] + k[6][0]) / 2) / sw
    l_c, r_c = k[3][2], k[4][2]
    eye_d = abs(k[1][0] - k[2][0])
    profile = (min(l_c, r_c) < 0.3 <= 0.5 <= max(l_c, r_c) and min(k[1][2], k[2][2]) >= 0.3 and eye_d > 1
               and abs(k[0][0] - (k[1][0] + k[2][0]) / 2) / eye_d >= 0.10)
    return rel, profile


def degrade(img, rng):
    h, w = img.shape[:2]
    s = rng.uniform(0.25, 0.5)
    small = cv2.resize(img, (max(8, int(w * s)), max(8, int(h * s))), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def main():
    rng = random.Random(SEED)
    pose = YOLO(POSE_MODEL)
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(V1, OUT)                     # bắt đầu từ SCB (đã chia theo nguồn)
    counts = {}

    for f in sorted(os.listdir(DS03)):
        m = re.match(r"v_(c\d)_((?:s\d_?)+)", f)
        if not f.endswith(".MOV") or not m:
            continue
        act = CLASSES[m.group(1)]
        subjects = [int(s) for s in re.findall(r"s(\d)", m.group(2))]
        role = {"left": "normal", "right": "normal"}
        for s in subjects:
            role["left" if s % 2 else "right"] = act
        # người ngồi trái là sv lẻ, phải là sv chẵn; người còn lại thuộc cặp (1,2),(3,4)...
        pair = (subjects[0] + 1) // 2
        side_subject = {"left": 2 * pair - 1, "right": 2 * pair}

        frames = {"left": [], "right": []}       # (crop, rel, profile)
        cap = cv2.VideoCapture(os.path.join(DS03, f))
        n = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            if n % 3 == 0:
                s = cv2.resize(fr, (960, 540))
                r = pose(s, imgsz=960, conf=0.25, verbose=False)[0]
                for k, b in zip(r.keypoints.data.cpu().numpy(), r.boxes.xyxy.tolist()):
                    side = "left" if (b[0] + b[2]) / 2 < 480 else "right"
                    rel, profile = face_signals(k)
                    crop = crop_person(s, b)
                    if rel is not None and crop is not None:
                        frames[side].append((crop, rel, profile))
            n += 1

        for side, items in frames.items():
            if not items or role[side] not in ("normal", "look"):
                continue
            split = subject_split(side_subject[side])
            med = float(np.median([rel for _, rel, _ in items]))
            for i, (crop, rel, profile) in enumerate(items):
                dev = abs(rel - med)
                if role[side] == "look" and (profile or dev >= 0.2):
                    label = "turn"
                elif dev < 0.07 and not profile:
                    label = "normal"
                else:
                    continue
                d = os.path.join(OUT, split, label)
                os.makedirs(d, exist_ok=True)
                name = f"ds03_{os.path.splitext(f)[0]}_{side}_{i}"
                cv2.imwrite(os.path.join(d, name + ".jpg"), crop)
                counts[(split, label)] = counts.get((split, label), 0) + 1
                if split != "test":
                    cv2.imwrite(os.path.join(d, name + "_lowres.jpg"), degrade(crop, rng))
                    counts[(split, label)] += 1

    for split in ("train", "val", "test"):
        tot = {c: len(os.listdir(os.path.join(OUT, split, c))) for c in ("normal", "turn")}
        added = {c: counts.get((split, c), 0) for c in ("normal", "turn")}
        print(f"{split:5s}: tổng turn={tot['turn']:5d} normal={tot['normal']:5d} | từ DS-03: turn={added['turn']} normal={added['normal']}")


if __name__ == "__main__":
    main()
