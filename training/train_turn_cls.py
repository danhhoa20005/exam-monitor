"""
Train model PHÂN LOẠI quay đầu trên ảnh cắt từng thí sinh (turn / normal).

Chạy:
    python train_turn_cls.py
    python train_turn_cls.py --model yolo11m-cls.pt --name turn_cls_v2

Sau khi train, script đánh giá trên tập TEST (lớp học chưa từng thấy) và in
Precision / Recall / F1 của lớp "turn" -> số liệu cho báo cáo.
"""
import argparse
import os
from multiprocessing import freeze_support

from ultralytics import YOLO

from training_paths import DATASET_DIR, MODELS_DIR

DATA = f"{DATASET_DIR}/turn_cls"


def evaluate(weights, split="test", data=DATA, prefix="", label="TẤT CẢ", threshold=0.5):
    """prefix: chỉ chấm ảnh có tên bắt đầu bằng prefix (vd 'ds03_' = ảnh phòng thi thật)."""
    model = YOLO(weights)
    names = model.names
    turn_idx = next(k for k, v in names.items() if v == "turn")
    tp = fp = fn = tn = 0
    for true_cls in ("normal", "turn"):
        d = os.path.join(data, split, true_cls)
        files = [os.path.join(d, f) for f in os.listdir(d) if f.startswith(prefix)]
        for i in range(0, len(files), 256):
            for r in model(files[i:i + 256], imgsz=224, device=0, verbose=False):
                pred = "turn" if float(r.probs.data[turn_idx]) >= threshold else "normal"
                if true_cls == "turn":
                    tp += pred == "turn"
                    fn += pred != "turn"
                else:
                    fp += pred == "turn"
                    tn += pred != "turn"
    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    p = tp / max(1, tp + fp)
    r = tp / max(1, tp + fn)
    f1 = 2 * p * r / max(1e-9, p + r)
    print(f"\n===== KẾT QUẢ TRÊN TẬP {split.upper()} ({label}) =====")
    print(f"Accuracy           : {acc:.3f}")
    print(f"Lớp turn Precision : {p:.3f}   (trong các lần báo quay đầu, bao nhiêu % đúng)")
    print(f"Lớp turn Recall    : {r:.3f}   (trong các ca quay đầu thật, bắt được bao nhiêu %)")
    print(f"Lớp turn F1        : {f1:.3f}")
    print(f"Ma trận nhầm lẫn   : TP={tp} FN={fn} FP={fp} TN={tn}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolo11s-cls.pt")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--name", default="turn_cls_v1")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--patience", type=int, default=15)
    args = ap.parse_args()

    model = YOLO(args.model)  # pretrained ImageNet
    model.train(
        data=args.data,

        # ===== TRAIN =====
        epochs=args.epochs,
        imgsz=224,
        batch=64,
        device=0,

        # ===== LOAD DATA =====
        workers=4,
        cache="ram",

        # ===== TRAIN QUALITY =====
        patience=args.patience,
        amp=True,
        optimizer="auto",
        cos_lr=True,
        dropout=0.2,            # chống overfit (behavior_v1 bị overfit từ epoch 54)
        fliplr=0.5,
        seed=42,

        # ===== OUTPUT =====
        project=f"{MODELS_DIR}",
        name=args.name,
    )
    best = f"{model.trainer.save_dir}/weights/best.pt"
    evaluate(best, data=args.data)
    evaluate(best, data=args.data, prefix="ds03_", label="CHỈ ẢNH PHÒNG THI DS-03")
    print(f"\nTrọng số tốt nhất: {best}")


if __name__ == "__main__":
    freeze_support()
    main()
