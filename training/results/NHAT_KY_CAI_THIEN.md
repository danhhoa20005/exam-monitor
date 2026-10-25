# Nhật ký cải thiện hệ thống phát hiện gian lận

Bộ đánh giá: DS-03 (Student Cheating Behavior Dataset, Hashemite University, 37 video, 8 sinh viên).
Mỗi (video, người) là 1 mẫu. Chia theo sinh viên: **dev = sv 1–4** (dùng để chỉnh), **test = sv 5–8** (chấm điểm cuối).
Kiểm tra phụ: `test/classroom.mp4` (camera CCTV toàn cảnh, thí sinh áo đỏ gian lận ~f1400–1950).

## Trước khi bắt đầu 10 vòng (các bản sửa đã có)
| Phiên bản | Nhìn bài bạn | Bình thường bị báo nhầm | Ghi chú |
|---|---|---|---|
| Ban đầu | 0/8 | 0/33 | yaw = None khi một tai bị che |
| + yaw khi tai bị che, giới hạn kích thước | 5/8 | 0/33 | |
| + mốc trung vị, xác nhận bằng mắt | 7/8 | 0/33 | sót v_c3_s2 (liếc trong lúc lấy mốc) |
| + reset khi đổi nguồn video (web) | — | — | sửa lỗi đảo ngược kết quả trên web |

## Vòng 1 — ngưỡng tạo track ByteTrack 0.6 → 0.5
- Lý do: người bị bàn che có độ tin cậy 0.49–0.67 → track ra đời muộn vài giây → lấy mốc đúng lúc đang quay đầu.
- DS-03: nhìn bài bạn 7/8, báo nhầm 0/33 (không đổi). classroom.mp4 (chỉ luật): 3/3, không báo nhầm mới.
- Quyết định: **giữ**.

## Vòng 2 — thêm phát hiện dùng điện thoại (YOLO11m COCO "cell phone" sát cổ tay)
- Luật: điện thoại cách cổ tay ≤ 0.5 lần độ rộng vai, làm mượt theo thời gian, kéo dài ≥ 1.0 s → REVIEW lý do PHONE.
- Chọn khoảng cách trên dev: điện thoại gần cổ tay ≥30% khung ở 7/9 người dùng điện thoại, 0/17 người bình thường.
- Kết quả (PHONE_CONF=0.2): điện thoại 1/17 → **13/17**; nhìn bài bạn 7/8; dev báo nhầm 0/17; **test báo nhầm 4/16**
  (người cầm bút dạ / bút bị nhận nhầm là điện thoại ở độ tin cậy thấp). classroom.mp4: không báo nhầm mới.
- Quyết định: giữ tính năng, chỉnh ngưỡng tin cậy ở vòng 3.

## Vòng 3 — ngưỡng tin cậy điện thoại 0.2 → 0.3
- Quy tắc chọn (chỉ dùng dev): ngưỡng cao nhất vẫn giữ recall điện thoại trên dev (0.2: 7/9, 0.3: 7/9, 0.4: 6/9) → 0.3.
- Lưu ý trung thực: các báo nhầm ở test đã được nhìn thấy ở vòng 2 trước khi chọn ngưỡng này.
- Kết quả vòng 3: test báo nhầm 4/16 → 3/16, điện thoại 12/17. Ba báo nhầm còn lại đều là PHONE ở người cầm bút viết bài.

## Vòng 4 — train turn_cls v2 (SCB + ảnh cắt DS-03 sv 1–3, kèm bản thu nhỏ mô phỏng CCTV)
- Nhãn DS-03 suy từ hình học khuôn mặt (mặt đủ lớn), khung lưng chừng bị bỏ; sv 4 = val, sv 5–8 = test.
- Trên ảnh phòng thi DS-03 (test): v1 Precision 0.12 / Recall 0.012 / F1 0.02 → **v2 Precision 0.955 / Recall 0.26 / F1 0.41**.
- Trên toàn bộ tập test (SCB + DS-03): F1 0.53 (giữ nguyên so với v1 trên SCB).

## Vòng 5 — lọc hình dạng khung điện thoại
- Đo trên dev: điện thoại thật nhỏ & dài (diện tích/vai² p90 0.043, tỉ lệ dài/rộng p10 1.7);
  bàn tay cầm bút nhận nhầm to & vuông (diện tích p10 0.053, tỉ lệ p50 1.1).
- Luật: chỉ tính khung có diện tích ≤ 0.05 vai² và tỉ lệ dài/rộng ≥ 1.3.
- Kết quả: **báo nhầm 0/33** (test 0/16), điện thoại 11/17, nhìn bài bạn 7/8, Precision tổng 1.00, Recall mọi hành vi 23/41.
- Quyết định: **giữ**.

## Vòng 6 — ghép turn_cls v2 vào hệ thống (ngưỡng 0.7)
- DS-03: nhìn bài bạn 8/8 (bắt thêm v_c3_s2), báo nhầm 0/33.
- classroom.mp4: **nhiều báo nhầm mới** — thí sinh áo đỏ bị báo cả khi đang làm bài (f105, f942...).
- Quyết định: chưa dùng được ở camera toàn cảnh → vòng 7.

## Vòng 7 — nâng ngưỡng turn_cls 0.7 → 0.85 / 0.92
- Không đủ: thí sinh áo đỏ vẫn bị báo ở đoạn bình thường kể cả ở 0.92.
- Nguyên nhân: từ góc camera đó, tư thế bình thường của anh ấy đã nghiêng → model (chỉ nhìn ảnh) luôn thấy "quay đầu".
- Quyết định: không giữ; cần mốc riêng từng người cho model (vòng 8).

## Vòng 8 — mốc riêng của từng thí sinh cho turn_cls
- P(turn) bình thường của mỗi người = trung vị lúc lấy mốc; chỉ tính quay đầu khi vượt mốc ≥ 0.4 và ≥ 0.7.
- classroom.mp4: hết báo nhầm ở thí sinh áo đỏ; còn 2 báo nhầm do AI (#32 cúi viết, #13 nhìn giám thị).
- DS-03: 7/8, 0/33 (v_c3_s2 lại sót vì liếc ngay lúc lấy mốc).

## Vòng 9 — siết turn_cls: ngưỡng 0.8, vượt mốc ≥ 0.5
- classroom.mp4: thí sinh áo đỏ 3/3, thí sinh áo tím 4 lượt quay đầu (chỉ AI bắt được), hết #32; còn #13 (ngẩng nhìn giám thị đi ngang).
- Quyết định: **giữ** làm cấu hình cuối.

## Vòng 10 — chấm điểm cuối (cấu hình chốt)
| Tập | Nhìn bài bạn | Điện thoại | Đổi bài | Phao | Báo nhầm người bình thường | Precision |
|---|---|---|---|---|---|---|
| dev (sv 1–4) | 3/4 | 6/9 | 0/4 | 1/4 | 0/17 | 1.00 |
| **test (sv 5–8)** | **4/4** | **5/8** | 3/4 | 1/4 | **0/16** | **1.00** |
| tất cả | 7/8 | 11/17 | 3/8 | 2/8 | 0/33 | 1.00 |

So với lúc bắt đầu đánh giá DS-03: nhìn bài bạn 0/8 → 7/8, điện thoại 0/17 → 11/17, mọi hành vi 2/41 → 23/41, báo nhầm vẫn 0/33.
Trên DS-03, luật và luật+AI cho kết quả như nhau; turn_cls v2 chỉ tạo khác biệt ở camera toàn cảnh (classroom.mp4).
