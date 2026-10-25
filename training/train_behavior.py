"""
Train YOLO phát hiện hành vi thí sinh: BowHead (cúi đầu), TurnHead (quay đầu).

Chạy:
    python train_behavior.py                       # cấu hình mặc định (yolo11s, 960)
    python train_behavior.py --model yolo11m.pt --name behavior_v2
    python train_behavior.py --smoke               # chạy thử 1 epoch để kiểm tra pipeline

Sau khi train xong, script tự đánh giá trên tập TEST (các nguồn chưa từng thấy)
và in Precision / Recall / mAP từng lớp -> dùng số này cho báo cáo.
"""
import argparse
from multiprocessing import freeze_support

from ultralytics import YOLO

from training_paths import DATASET_DIR, MODELS_DIR

DATA = f"{DATASET_DIR}/behavior/data.yaml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolo11s.pt", help="yolo11n/s/m.pt (RTX 4060 8GB: s hoặc m)")
    ap.add_argument("--imgsz", type=int, default=960, help="bằng kích thước lúc triển khai (backend dùng 960)")
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--name", default="behavior_v1")
    ap.add_argument("--smoke", action="store_true", help="1 epoch, 5%% dữ liệu: chỉ để kiểm tra chạy được")
    args = ap.parse_args()

    if args.smoke:
        args.epochs, args.imgsz, args.name = 1, 640, "behavior_smoke"

    model = YOLO(args.model)  # pretrained COCO

    model.train(
        data=DATA,

        # ===== TRAIN =====
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=0.80,             # tự chọn batch để dùng ~80% VRAM
        device=0,
        fraction=0.05 if args.smoke else 1.0,

        # ===== LOAD DATA =====
        workers=4,
        cache="ram",            # ~3GB RAM; ảnh gốc 1920x1080 giải nén chậm nếu đọc lại mỗi epoch

        # ===== TRAIN QUALITY =====
        patience=30,
        amp=True,
        optimizer="auto",
        cos_lr=True,
        close_mosaic=15,
        fliplr=0.5,             # an toàn: TurnHead không phân biệt quay trái/phải
        seed=42,

        # ===== OUTPUT =====
        project=f"{MODELS_DIR}",
        name=args.name,
        exist_ok=args.smoke,
    )

    # ===== ĐÁNH GIÁ TRÊN TẬP TEST (nguồn chưa từng thấy) =====
    best = YOLO(f"{model.trainer.save_dir}/weights/best.pt")
    m = best.val(data=DATA, split="test", imgsz=args.imgsz, device=0, plots=True,
                 project=f"{MODELS_DIR}", name=f"{args.name}_test", exist_ok=True)

    print("\n===== KẾT QUẢ TRÊN TẬP TEST =====")
    print(f"{'Lớp':10s} {'Precision':>9s} {'Recall':>7s} {'mAP50':>7s} {'mAP50-95':>9s}")
    for i, c in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        print(f"{best.names[int(c)]:10s} {p:9.3f} {r:7.3f} {ap50:7.3f} {ap:9.3f}")
    print(f"{'Tất cả':10s} {m.box.mp:9.3f} {m.box.mr:7.3f} {m.box.map50:7.3f} {m.box.map:9.3f}")
    print(f"\nTrọng số tốt nhất: {model.trainer.save_dir}/weights/best.pt")


if __name__ == "__main__":
    freeze_support()
    main()
