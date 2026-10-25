# Huấn luyện & đánh giá mô hình

Thư mục này chứa toàn bộ quy trình dữ liệu → train → đánh giá của nhóm. Kết quả các lần train và
đánh giá đã thực hiện nằm trong [`results/`](results/), nhật ký 10 vòng cải thiện ở
[`results/NHAT_KY_CAI_THIEN.md`](results/NHAT_KY_CAI_THIEN.md).

## 1. Hệ thống dùng những model nào

| Model | Vai trò | Nguồn |
|---|---|---|
| `yolo11l-pose.pt` | Tìm thí sinh + 17 điểm khớp (nền tảng) | Ultralytics, backend tự tải |
| `yolo11m.pt` | Phát hiện điện thoại (lớp COCO `cell phone`) sát cổ tay | Ultralytics, backend tự tải |
| **`turn_cls.pt`** | Phân loại "đang quay đầu" trên ảnh cắt từng thí sinh (tín hiệu phụ) | **Nhóm train** — `turn_cls_v2`, có sẵn trong `backend/models/` |

Các model nhóm train nhưng không đưa vào hệ thống (kết quả vẫn lưu để so sánh):
`student_v3` (phát hiện "student", ảnh 256 px — mAP bị thổi phồng do rò rỉ dữ liệu) và
`behavior_v1` (phát hiện BowHead/TurnHead trên cả khung hình — mAP50 0.38, kém trên video phòng thi).

## 2. Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
```

Mọi dữ liệu, model train ra và kết quả nằm trong **thư mục làm việc** (mặc định `training/workspace/`,
đã nằm trong `.gitignore`). Đổi chỗ bằng biến môi trường:

```bash
$env:TRAINING_WORKDIR = "D:/HTTM"   # PowerShell; Linux/macOS: export TRAINING_WORKDIR=/data/httm
```

```
<TRAINING_WORKDIR>/
  dataset/_raw/scb_bowturnhead/   SCB BowTurnHead (giải nén)
  dataset/_raw/ds03/              37 video DS-03 (.MOV)
  dataset/behavior|turn_cls|turn_cls_v2/   sinh ra bởi các script prepare_*
  models/                         kết quả train
  result/                         kết quả đánh giá
  test/classroom.mp4              video kiểm thử CCTV
```

## 3. Tải dữ liệu

| Dataset | Dùng cho | Nguồn | Giấy phép |
|---|---|---|---|
| **SCB BowTurnHead** (2 410 ảnh lớp học, nhãn BowHead/TurnHead) | train | Hugging Face `wintonYF/SCB-Dataset` → `SCB_BowTurnHead_20250509/SCB_BowTurnHead_20250509.zip` (315 MB) | học thuật, phi thương mại — trích dẫn arXiv:2304.02488 |
| **DS-03 Student Cheating Behavior** (37 video thi giấy, 8 sinh viên, 5 hành vi) | train (sv 1–3) / val (sv 4) / **test (sv 5–8)** | Kaggle `fairouzfarouq/student-cheating-behavior-dataset` (1.33 GB) | công bố cho nghiên cứu (Hashemite University) |

Giải nén SCB vào `dataset/_raw/scb_bowturnhead/`, chép các file `.MOV` của DS-03 vào `dataset/_raw/ds03/`.

> Lưu ý tên file DS-03: thứ tự hoạt động trong README gốc **không khớp** tên file. Ánh xạ đã kiểm tra bằng mắt:
> `c1` điện thoại, `c2` đổi bài, `c3` nhìn bài bạn, `c4` dùng phao, `c5` không gian lận.
> Sinh viên số lẻ ngồi bên trái, số chẵn bên phải.

## 4. Train model quay đầu `turn_cls` (model đang dùng)

```bash
cd training
python prepare_behavior_dataset.py      # SCB -> dataset/behavior, chia theo nguồn (không rò rỉ)
python prepare_turn_cls.py              # ảnh cắt từng người (YOLO11-Pose) -> dataset/turn_cls
python prepare_turn_cls_v2.py           # + ảnh cắt DS-03 sv1-3 & bản thu nhỏ mô phỏng CCTV -> dataset/turn_cls_v2
python train_turn_cls.py --data <TRAINING_WORKDIR>/dataset/turn_cls_v2 --name turn_cls_v2
```

`train_turn_cls.py` tự chấm điểm trên tập test (toàn bộ và riêng ảnh phòng thi DS-03).
Kết quả của nhóm (`turn_cls_v2`, test DS-03 sv 5–8): Precision 0.955, Recall 0.26, F1 0.41
(v1 chỉ train trên SCB: F1 0.02). Đưa vào hệ thống:

```bash
copy <TRAINING_WORKDIR>\models\turn_cls_v2\weights\best.pt ..\backend\models\turn_cls.pt
```

Hàm cắt ảnh `crop_person()` trong `prepare_turn_cls.py` phải giống hệt bản trong
`backend/app/inference/turn_classifier.py`, nếu không model sẽ thấy ảnh khác lúc train.

## 5. Các thí nghiệm khác

```bash
python train.py                         # student detector (student_v3) trên dataset/student
python test.py                          # chạy student_v3 trên test/classroom.mp4
python train_behavior.py                # behavior_v1: YOLO11s phát hiện BowHead/TurnHead
python test_behavior.py                 # chạy behavior_v1 trên video
python extract_frames.py video.mp4 --every 1.5   # trích frame để tự gán nhãn thêm
```

## 6. Đánh giá cả hệ thống trên video có nhãn

```bash
python eval_videos.py --name ket_qua_moi                 # toàn bộ DS-03, 2 cấu hình: chỉ luật / luật + AI
python eval_videos.py --split dev --modes ai             # chỉ sv 1-4 (dùng để chỉnh thông số)
python eval_videos.py --split test --modes ai            # chỉ sv 5-8 (chấm điểm cuối, không chỉnh theo)
python eval_videos.py --videos thu_muc --labels nhan.csv # video của nhóm; nhan.csv: filename,left,right
```

Mỗi (video, người) là một mẫu: người gian lận phải bị báo REVIEW, người bình thường không được báo.
Kết quả cấu hình cuối (`results/eval/r10_final.csv`):

| Tập | Nhìn bài bạn | Điện thoại | Đổi bài | Phao | Báo nhầm người bình thường | Precision |
|---|---|---|---|---|---|---|
| dev (sv 1–4) | 3/4 | 6/9 | 0/4 | 1/4 | 0/17 | 1.00 |
| **test (sv 5–8)** | **4/4** | **5/8** | 3/4 | 1/4 | **0/16** | **1.00** |

## 7. Nguồn tham khảo
- Ultralytics YOLO11 (pose, detect, classify) — https://docs.ultralytics.com
- Thuật toán gốc độ lệch mũi/vai: repo `dyingangell/Cheating-detection-YOLO`
- SCB-Dataset — Yang Fan et al., arXiv:2304.02488
- Student Cheating Behavior Dataset (DS-03) — Hashemite University, Kaggle
