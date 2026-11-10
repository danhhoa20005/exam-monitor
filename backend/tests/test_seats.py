"""
FT-01: định danh thí sinh theo vị trí bàn thi (ghế) cố định.

ByteTrack đổi ID khi thí sinh bị che (classroom.mp4: 41 ID cho ~25 người). Ghế giữ số cố định:
ID mới xuất hiện đúng chỗ một ghế đang trống sẽ nhận lại số ghế đó (và mốc tư thế đã lấy).
"""
from app.inference.seats import SeatRegistry

A = (0.10, 0.20, 0.20, 0.50)        # student at the left
B = (0.60, 0.20, 0.70, 0.50)        # student at the right


def test_same_track_keeps_its_seat():
    reg = SeatRegistry()
    s1 = reg.assign([(1, A)])[1][0]
    assert reg.assign([(1, A)])[1][0] == s1


def test_new_id_at_vacated_seat_takes_it_over():
    reg = SeatRegistry()
    seat = reg.assign([(1, A), (2, B)])[1][0]
    nudged = (0.11, 0.21, 0.21, 0.51)                 # tracker lost #1, same person comes back as #7
    seat7, inherited_from = reg.assign([(7, nudged), (2, B)])[7]
    assert seat7 == seat
    assert inherited_from == 1


def test_far_away_new_id_gets_a_new_seat():
    reg = SeatRegistry()
    seat_a = reg.assign([(1, A)])[1][0]
    seat_c, inherited_from = reg.assign([(1, A), (3, (0.40, 0.60, 0.50, 0.90))])[3]
    assert seat_c != seat_a
    assert inherited_from is None


def test_occupied_seat_is_not_stolen():
    """Giám thị đi ngang qua sát một thí sinh đang ngồi: không được nhận ghế của thí sinh đó."""
    reg = SeatRegistry()
    seat_a = reg.assign([(1, A)])[1][0]
    out = reg.assign([(1, A), (5, (0.11, 0.18, 0.21, 0.55))])
    assert out[1][0] == seat_a
    assert out[5][0] != seat_a


def test_seat_numbers_start_at_one_and_reset():
    reg = SeatRegistry()
    out = reg.assign([(1, A), (2, B)])
    assert sorted(s for s, _ in out.values()) == [1, 2]
    reg.reset()
    assert reg.assign([(9, B)])[9][0] == 1


def test_standing_person_does_not_take_a_seated_students_seat():
    """classroom.mp4 f1356: giám thị đi ngang che thí sinh -> khung đứng (cao gấp đôi) không được nhận ghế trống."""
    reg = SeatRegistry()
    seat_a = reg.assign([(1, A)])[1][0]
    standing = (0.10, 0.05, 0.21, 0.75)               # same spot, much taller box
    seat_x, inherited_from = reg.assign([(8, standing)])[8]
    assert seat_x != seat_a
    assert inherited_from is None


# ---------- pipeline: a new track id gets the seat number but recalibrates ----------
from app.inference import tracking_core
from app.inference.pose_behavior import CandidateTrackState


def test_pipeline_keeps_seat_number_but_does_not_reuse_calibration(monkeypatch):
    """Kế thừa mốc tư thế đã thử và bỏ: trên classroom.mp4 nó sinh 2 báo nhầm, không thêm ca đúng nào."""
    monkeypatch.setattr(tracking_core.SessionInferencePipeline, "_init_yolo", lambda self: None)
    p = tracking_core.SessionInferencePipeline("seat-test")
    p._apply_seats([(1, A)])
    old = CandidateTrackState(1)
    old.is_calibrated = True
    p.pose_engine.track_states[1] = old

    seats = p._apply_seats([(7, (0.11, 0.21, 0.21, 0.51))])
    assert seats[7] == 1
    assert 7 not in p.pose_engine.track_states            # track 7 will calibrate itself
