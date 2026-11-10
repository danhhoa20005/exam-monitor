import { MonitoringEvent } from '../types/monitoring';

// FT-10 exam session report: a printable A4 page; the browser's print dialog saves it as PDF
// (keeps Vietnamese text correct without shipping fonts to the backend).

export interface StudentStat {
  label: string;          // "Ghế 05" (seat) or "ID 12" when no seat is known
  maxScore: number;       // highest risk score seen this session
  reviewFrames: number;   // frames spent in REVIEW
  reasons: string[];
  firstSeenMs: number;
  lastSeenMs: number;
}

interface ReportInput {
  sessionId: string;
  startedAtMs: number;
  sensitivity: number;
  students: StudentStat[];
  events: MonitoringEvent[];
}

const REASON_VI: Record<string, string> = {
  TURNING: 'Quay đầu / nhìn bài bạn',
  PHONE: 'Dùng điện thoại',
  UNDER_DESK: 'Cúi gập nhìn dưới bàn',
  BENDING: 'Cúi người',
};

const DECISION_VI: Record<string, string> = {
  PENDING: 'Chưa xử lý',
  NEEDS_REVIEW: 'Cần xem xét',
  CONFIRMED: 'Xác nhận vi phạm',
  DISMISSED: 'Bỏ qua',
};

const esc = (s: unknown) =>
  String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
const reasonsVi = (rs: string[]) => rs.map(r => REASON_VI[r] || r).join(', ') || '—';
const time = (ms: number) => new Date(ms).toLocaleTimeString('vi-VN');

export function buildSessionReportHtml({ sessionId, startedAtMs, sensitivity, students, events }: ReportInput): string {
  const ranked = [...students].sort((a, b) => b.maxScore - a.maxScore || b.reviewFrames - a.reviewFrames);
  const confirmed = events.filter(e => e.review_status === 'CONFIRMED').length;
  const pending = events.filter(e => e.review_status === 'PENDING' || e.review_status === 'NEEDS_REVIEW').length;
  const studentRows = ranked.map((s, i) => `
    <tr class="${s.maxScore >= 80 ? 'hi' : ''}">
      <td>${i + 1}</td><td>${esc(s.label)}</td><td class="num">${s.maxScore}</td>
      <td class="num">${(s.reviewFrames / 10).toFixed(1)}</td><td>${esc(reasonsVi(s.reasons))}</td>
    </tr>`).join('');
  const eventRows = [...events].sort((a, b) => a.start_ms - b.start_ms).map((e, i) => `
    <tr>
      <td>${i + 1}</td><td>${time(e.start_ms)}</td>
      <td>${esc(e.seat_id ? `Ghế ${String(e.seat_id).padStart(2, '0')}` : `ID ${e.track_id}`)}</td>
      <td>${esc(reasonsVi(e.reasons))}</td><td class="num">${(e.duration_ms / 1000).toFixed(1)}</td>
      <td>${esc(DECISION_VI[e.review_status] || e.review_status)}</td>
      <td>${e.evidence_url ? `<a href="${esc(e.evidence_url)}">Xem clip</a>` : '—'}</td>
    </tr>`).join('');

  return `<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Biên bản ca thi ${esc(sessionId)}</title>
<style>
  @page { size: A4; margin: 16mm; }
  body { font-family: Arial, sans-serif; color: #111; font-size: 12px; }
  h1 { text-align: center; font-size: 18px; margin: 0 0 4px; }
  .sub { text-align: center; color: #555; margin-bottom: 14px; }
  h2 { font-size: 14px; margin: 18px 0 6px; border-bottom: 1px solid #999; padding-bottom: 3px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid #bbb; padding: 4px 6px; text-align: left; vertical-align: top; }
  th { background: #1f4e79; color: #fff; }
  .num { text-align: right; }
  tr.hi td { background: #fde8e8; }
  .meta td { border: none; padding: 2px 6px; }
  .sign { display: flex; justify-content: space-around; margin-top: 40px; text-align: center; }
  .sign div { width: 40%; } .sign i { color: #777; }
  .note { color: #666; font-size: 11px; margin-top: 8px; }
</style></head><body>
<h1>BIÊN BẢN GIÁM SÁT CA THI</h1>
<div class="sub">Hệ thống giám sát gian lận phòng thi bằng camera (AI hỗ trợ giám thị)</div>
<table class="meta">
  <tr><td><b>Mã phiên:</b> ${esc(sessionId)}</td><td><b>Bắt đầu ghi nhận:</b> ${new Date(startedAtMs).toLocaleString('vi-VN')}</td></tr>
  <tr><td><b>Lập biên bản lúc:</b> ${new Date().toLocaleString('vi-VN')}</td><td><b>Độ nhạy cảnh báo:</b> ${sensitivity}/5</td></tr>
  <tr><td><b>Số thí sinh được theo dõi:</b> ${students.length}</td><td><b>Sự kiện nghi vấn:</b> ${events.length} (xác nhận vi phạm: ${confirmed}, chưa xử lý / cần xem xét: ${pending})</td></tr>
</table>
<h2>1. Thí sinh theo mức độ nghi vấn</h2>
<table><tr><th>#</th><th>Thí sinh</th><th>Điểm nghi vấn cao nhất</th><th>Thời gian bị cảnh báo (s)</th><th>Hành vi ghi nhận</th></tr>
${studentRows || '<tr><td colspan="5">Không có dữ liệu.</td></tr>'}</table>
<h2>2. Danh sách sự kiện nghi vấn</h2>
<table><tr><th>#</th><th>Thời điểm</th><th>Thí sinh</th><th>Hành vi</th><th>Thời lượng (s)</th><th>Quyết định giám thị</th><th>Bằng chứng</th></tr>
${eventRows || '<tr><td colspan="7">Không có sự kiện nào.</td></tr>'}</table>
<p class="note">Cảnh báo do AI đưa ra chỉ mang tính hỗ trợ; kết luận vi phạm do giám thị quyết định sau khi xem clip bằng chứng.</p>
<div class="sign"><div><b>Giám thị 1</b><br><i>(Ký, ghi rõ họ tên)</i></div><div><b>Giám thị 2</b><br><i>(Ký, ghi rõ họ tên)</i></div></div>
</body></html>`;
}

export function openSessionReport(input: ReportInput) {
  const w = window.open('', '_blank');
  if (!w) {
    alert('Trình duyệt đã chặn cửa sổ mới. Hãy cho phép pop-up để in biên bản.');
    return;
  }
  w.document.write(buildSessionReportHtml(input));
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 300);   // "Lưu dưới dạng PDF" in the print dialog
}
