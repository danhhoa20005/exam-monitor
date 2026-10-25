"""
Chuẩn bị dataset hành vi (BowHead / TurnHead) để train YOLO.

- Nguồn chính: SCB_BowTurnHead_20250509 (Hugging Face: wintonYF/SCB-Dataset)
- Nguồn phụ (tuỳ chọn): frame phòng thi nhóm tự gán nhãn, định dạng YOLO,
  đặt trong <TRAINING_WORKDIR>/dataset/_labeled_exam/<ten_video>/{images,labels}

Chia train/val/test THEO NGUỒN (cùng một video/lớp học chỉ nằm ở 1 tập)
để tránh rò rỉ dữ liệu như dataset student cũ (27-32% ảnh val/test trùng train).
Ảnh giữ nguyên độ phân giải gốc, không augment trước (YOLO tự augment khi train).
"""
import os
import random
import shutil
from collections import Counter, defaultdict

from training_paths import DATASET_DIR

SCB_ROOT = f"{DATASET_DIR}/_raw/scb_bowturnhead/SCB_BowTurnHead_20250509/SCB5-Turn-Bow-Head-2024-9-17"
EXAM_ROOT = f"{DATASET_DIR}/_labeled_exam"
OUT = f"{DATASET_DIR}/behavior"
NAMES = ["BowHead", "TurnHead"]

SPLIT_RATIO = {"train": 0.70, "val": 0.15, "test": 0.15}
SEED = 42


def scb_group(filename):
    # 0001001.jpg -> "0001" (4 số đầu là mã nguồn), 133_0001.jpg -> "133"
    stem = os.path.splitext(filename)[0]
    return "scb_" + (stem.split("_")[0] if "_" in stem else stem[:4])


def collect():
    """Trả về {group: [(img_path, label_path), ...]}"""
    groups = defaultdict(list)
    for split in ("train", "val"):
        img_dir = os.path.join(SCB_ROOT, "images", split)
        for f in sorted(os.listdir(img_dir)):
            lbl = os.path.join(SCB_ROOT, "labels", split, os.path.splitext(f)[0] + ".txt")
            groups[scb_group(f)].append((os.path.join(img_dir, f), lbl))

    if os.path.isdir(EXAM_ROOT):
        for video in sorted(os.listdir(EXAM_ROOT)):
            img_dir = os.path.join(EXAM_ROOT, video, "images")
            if not os.path.isdir(img_dir):
                continue
            for f in sorted(os.listdir(img_dir)):
                lbl = os.path.join(EXAM_ROOT, video, "labels", os.path.splitext(f)[0] + ".txt")
                groups["exam_" + video].append((os.path.join(img_dir, f), lbl))
    return groups


def class_counts(items):
    c = Counter()
    for _, lbl in items:
        if os.path.exists(lbl):
            with open(lbl) as fh:
                c.update(line.split()[0] for line in fh if line.strip())
    return c


def split_groups(groups):
    """Chia theo group, cân số ảnh gần đúng tỉ lệ; nhóm lớn nhất xếp trước."""
    rng = random.Random(SEED)
    keys = list(groups)
    rng.shuffle(keys)
    keys.sort(key=lambda k: -len(groups[k]))
    total = sum(len(v) for v in groups.values())
    target = {s: r * total for s, r in SPLIT_RATIO.items()}
    filled = {s: 0 for s in SPLIT_RATIO}
    assign = {}
    for k in keys:
        # đưa group vào tập đang thiếu nhiều nhất so với mục tiêu
        s = max(SPLIT_RATIO, key=lambda s: target[s] - filled[s])
        assign[k] = s
        filled[s] += len(groups[k])
    return assign


def main():
    groups = collect()
    assign = split_groups(groups)

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    report = {}
    for split in SPLIT_RATIO:
        os.makedirs(os.path.join(OUT, split, "images"))
        os.makedirs(os.path.join(OUT, split, "labels"))
        split_groups_ = [g for g, s in assign.items() if s == split]
        items = [it for g in split_groups_ for it in groups[g]]
        for g in split_groups_:
            for img, lbl in groups[g]:
                # tiền tố group để tên file không trùng giữa các nguồn
                name = f"{g}_{os.path.basename(img)}"
                shutil.copy2(img, os.path.join(OUT, split, "images", name))
                dst_lbl = os.path.join(OUT, split, "labels", os.path.splitext(name)[0] + ".txt")
                if os.path.exists(lbl):
                    shutil.copy2(lbl, dst_lbl)
                else:
                    open(dst_lbl, "w").close()  # ảnh không có đối tượng = ảnh nền
        report[split] = (len(items), split_groups_, class_counts(items))

    with open(os.path.join(OUT, "data.yaml"), "w", encoding="utf-8") as fh:
        fh.write(f"path: {OUT}\ntrain: train/images\nval: val/images\ntest: test/images\n\n")
        fh.write(f"nc: {len(NAMES)}\nnames: {NAMES}\n")

    print(f"Đã tạo dataset tại {OUT}")
    for split, (n, gs, cc) in report.items():
        per_cls = ", ".join(f"{NAMES[int(k)]}={v}" for k, v in sorted(cc.items()))
        print(f"  {split:5s}: {n:5d} ảnh | {len(gs):2d} nguồn | {per_cls}")
    print(f"  Kiểm tra rò rỉ: {len(assign)} nguồn, mỗi nguồn chỉ nằm trong đúng 1 tập.")


if __name__ == "__main__":
    main()
