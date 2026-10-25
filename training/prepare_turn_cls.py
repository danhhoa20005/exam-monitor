"""
Tạo dataset PHÂN LOẠI ảnh cắt từng thí sinh: turn (quay đầu) / normal.

Ý tưởng: trong hệ thống, YOLO11-Pose đã tìm được từng người. Model của nhóm chỉ cần
nhìn ảnh cắt của MỘT người và trả lời "có đang quay đầu không" -> dễ hơn nhiều so với
vừa tìm người vừa đoán hành vi trên cả khung hình (behavior_v1).

Cách tạo nhãn từ SCB BowTurnHead (đã chia theo nguồn ở dataset/behavior):
  1. Chạy YOLO11-Pose trên ảnh -> khung người (giống hệt lúc chạy thật trong backend)
  2. Gắn mỗi nhãn SCB vào khung người chứa nó nhiều nhất
       TurnHead -> turn ; BowHead -> normal (cúi viết bài là bình thường trong phòng thi)
  3. Người không có nhãn nào -> normal (có nhiễu vì SCB gán nhãn thiếu, nên giới hạn số lượng)
Ảnh cắt dùng ĐÚNG hàm crop_person() mà backend sẽ dùng, để train và chạy thật giống nhau.

Kết quả: <TRAINING_WORKDIR>/dataset/turn_cls/{train,val,test}/{normal,turn}/*.jpg
"""
import os
import random
import shutil
from collections import Counter

import cv2
from ultralytics import YOLO

from training_paths import DATASET_DIR, POSE_MODEL

SRC = f"{DATASET_DIR}/behavior"
OUT = f"{DATASET_DIR}/turn_cls"
POSE_MODEL = str(POSE_MODEL)
UNLABELED_PER_LABELED = 1.0   # số ảnh "normal không nhãn" tối đa so với số ảnh có nhãn
SEED = 42


def crop_person(img, box):
    """Cắt nửa trên cơ thể (đầu + vai) của một người, nới rộng 10% mỗi bên."""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    y2 = y1 + bh * 0.65                      # đầu + vai + tay trên bàn
    x1, x2 = x1 - 0.1 * bw, x2 + 0.1 * bw
    y1 = y1 - 0.1 * bh
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 16 or y2 - y1 < 16:
        return None
    return img[y1:y2, x1:x2]


def intersection_over_label(label, person):
    ix = max(0.0, min(label[2], person[2]) - max(label[0], person[0]))
    iy = max(0.0, min(label[3], person[3]) - max(label[1], person[1]))
    area = max(1e-6, (label[2] - label[0]) * (label[3] - label[1]))
    return ix * iy / area


def read_labels(path, w, h):
    out = []
    if os.path.exists(path):
        for line in open(path):
            p = line.split()
            if len(p) == 5:
                c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
                out.append((c, ((cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h)))
    return out


def main():
    rng = random.Random(SEED)
    pose = YOLO(POSE_MODEL)
    if os.path.exists(OUT):
        shutil.rmtree(OUT)

    for split in ("train", "val", "test"):
        img_dir = os.path.join(SRC, split, "images")
        labeled, unlabeled = [], []           # (crop, cls, name)
        for f in sorted(os.listdir(img_dir)):
            img = cv2.imread(os.path.join(img_dir, f))
            if img is None:
                continue
            h, w = img.shape[:2]
            labels = read_labels(os.path.join(SRC, split, "labels", os.path.splitext(f)[0] + ".txt"), w, h)
            r = pose(img, imgsz=960, conf=0.25, verbose=False)[0]
            persons = r.boxes.xyxy.tolist()

            assigned = {}
            for c, lb in labels:
                scores = [intersection_over_label(lb, p) for p in persons]
                if scores and max(scores) >= 0.6:
                    # khi nhiều người cùng chứa nhãn, chọn khung nhỏ nhất (người gần nhãn nhất)
                    cands = [i for i, s in enumerate(scores) if s >= 0.6]
                    i = min(cands, key=lambda i: (persons[i][2] - persons[i][0]) * (persons[i][3] - persons[i][1]))
                    assigned[i] = "turn" if c == 1 else "normal"

            for i, p in enumerate(persons):
                crop = crop_person(img, p)
                if crop is None:
                    continue
                item = (crop, assigned.get(i, "normal"), f"{os.path.splitext(f)[0]}_{i}.jpg")
                (labeled if i in assigned else unlabeled).append(item)

        rng.shuffle(unlabeled)
        keep = unlabeled[: int(len(labeled) * UNLABELED_PER_LABELED)]
        counts = Counter()
        for crop, cls, name in labeled + keep:
            d = os.path.join(OUT, split, cls)
            os.makedirs(d, exist_ok=True)
            cv2.imwrite(os.path.join(d, name), crop)
            counts[cls] += 1
        print(f"{split:5s}: turn={counts['turn']:5d} normal={counts['normal']:5d} "
              f"(có nhãn {len(labeled)}, không nhãn dùng {len(keep)}/{len(unlabeled)})")


if __name__ == "__main__":
    main()
