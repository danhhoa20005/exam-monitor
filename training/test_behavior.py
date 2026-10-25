"""
Chạy model hành vi đã train trên video phòng thi và lưu video kết quả để xem bằng mắt.

    python test_behavior.py                                   # mặc định: behavior_v1 + test/classroom.mp4
    python test_behavior.py --model <TRAINING_WORKDIR>/models/behavior_v2/weights/best.pt --video duong_dan/video.mp4
"""
import argparse

from ultralytics import YOLO

from training_paths import MODELS_DIR, RESULT_DIR, TEST_VIDEO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=f"{MODELS_DIR}/behavior_v1/weights/best.pt")
    ap.add_argument("--video", default=str(TEST_VIDEO))
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--conf", type=float, default=0.35)
    args = ap.parse_args()

    model = YOLO(args.model)
    results = model.predict(
        source=args.video,
        conf=args.conf,
        imgsz=args.imgsz,
        device=0,
        save=True,
        stream=True,
        verbose=False,
        project=f"{RESULT_DIR}",
        name="behavior_test",
        exist_ok=True,
    )

    # stream=True nên phải duyệt hết kết quả; đếm số khung có từng hành vi
    counts = {name: 0 for name in model.names.values()}
    frames = 0
    for r in results:
        frames += 1
        for c in set(int(x) for x in r.boxes.cls.tolist()):
            counts[model.names[c]] += 1

    print(f"\nĐã xử lý {frames} khung hình.")
    for name, n in counts.items():
        print(f"  Số khung có {name}: {n}")
    print(f"Video kết quả: {RESULT_DIR}/behavior_test/")


if __name__ == "__main__":
    main()
