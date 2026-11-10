import React, { useState } from 'react';
import { MonitoringEvent, EventReviewStatus } from '../../types/monitoring';
import { AlertTriangle, CheckCircle2, Eye, XCircle, Clock, Download, FileSpreadsheet, Film, FileText, Volume2, VolumeX } from 'lucide-react';

// The backend still records the 5 s after the alert, so ask before opening the clip
async function openEvidence(url: string, setNote: (msg: string) => void) {
  try {
    const res = await fetch(`${url}/status`);
    const { status } = await res.json();
    if (status === 'ready') {
      setNote('');
      window.open(url, '_blank', 'noopener');
    } else if (status === 'recording') {
      setNote('Đang ghi 5 giây sau sự kiện, thử lại sau vài giây...');
    } else {
      setNote('Không có clip (đã đạt giới hạn 50 clip/phiên hoặc phiên đã khởi động lại).');
    }
  } catch {
    setNote('Không kết nối được tới AI backend để lấy clip.');
  }
}

interface EventPanelProps {
  events: MonitoringEvent[];
  onUpdateStatus: (eventId: string, status: EventReviewStatus) => void;
  onExportCsv: () => void;
  onExportJson: () => void;
  onExportReport?: () => void;
  soundOn?: boolean;
  onToggleSound?: () => void;
}

export const EventPanel: React.FC<EventPanelProps> = ({
  events,
  onUpdateStatus,
  onExportCsv,
  onExportJson,
  onExportReport,
  soundOn,
  onToggleSound
}) => {
  const [clipNotes, setClipNotes] = useState<Record<string, string>>({});
  return (
    <div className="flex flex-col gap-3">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <AlertTriangle size={18} className="text-amber-400" />
          <h2 className="text-sm font-semibold text-slate-100 whitespace-nowrap">
            Nhật Ký Sự Kiện Nghi Vấn ({events.length})
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-1 whitespace-nowrap">
          {onToggleSound && (
            <button
              type="button"
              onClick={onToggleSound}
              aria-pressed={soundOn}
              className={`px-2 py-1 text-xs font-medium rounded-lg flex items-center gap-1 border transition-all ${
                soundOn
                  ? 'text-emerald-300 bg-emerald-950/40 hover:bg-emerald-900/50 border-emerald-800/60'
                  : 'text-slate-400 bg-slate-800/80 hover:bg-slate-700 border-slate-700'
              }`}
              title={soundOn ? 'Âm báo đang bật: kêu bíp khi có sự kiện nghi vấn mới. Bấm để tắt.' : 'Âm báo đang tắt. Bấm để bật.'}
            >
              {soundOn ? <Volume2 size={12} /> : <VolumeX size={12} />}
              <span>{soundOn ? 'Âm báo' : 'Tắt tiếng'}</span>
            </button>
          )}
        {events.length > 0 && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onExportCsv}
              className="px-2.5 py-1 text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700 border border-slate-700 rounded-lg flex items-center gap-1 transition-all"
              title="Xuất CSV"
            >
              <FileSpreadsheet size={12} />
              <span>CSV</span>
            </button>
            <button
              type="button"
              onClick={onExportJson}
              className="px-2.5 py-1 text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700 border border-slate-700 rounded-lg flex items-center gap-1 transition-all"
              title="Xuất JSON"
            >
              <Download size={12} />
              <span>JSON</span>
            </button>
            {onExportReport && (
              <button
                type="button"
                onClick={onExportReport}
                className="px-2.5 py-1 text-xs font-medium text-amber-200 bg-amber-950/50 hover:bg-amber-900/60 border border-amber-800/60 rounded-lg flex items-center gap-1 transition-all"
                title="Biên bản ca thi (in hoặc Lưu dưới dạng PDF)"
              >
                <FileText size={12} />
                <span>Biên bản</span>
              </button>
            )}
          </div>
        )}
        </div>
      </div>

      {/* Events List */}
      <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="p-6 text-center text-slate-500 text-xs bg-slate-900/40 rounded-xl border border-slate-800/60">
            Chưa ghi nhận sự kiện nghi vấn nào.
          </div>
        ) : (
          events.map(evt => {
            const isPending = evt.review_status === 'PENDING';
            const isConfirmed = evt.review_status === 'CONFIRMED';
            const isDismissed = evt.review_status === 'DISMISSED';
            const isNeedsReview = evt.review_status === 'NEEDS_REVIEW';

            return (
              <div
                key={evt.event_id}
                className={`p-3 rounded-xl border transition-all ${
                  isPending 
                    ? 'bg-rose-950/20 border-rose-500/40' 
                    : isConfirmed
                    ? 'bg-red-950/30 border-red-500/50'
                    : 'bg-slate-900/60 border-slate-800/80'
                }`}
              >
                {/* Event Title & Timestamp */}
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-rose-300 flex items-center gap-1.5">
                    <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 font-mono text-[10px]">
                      {evt.seat_id
                        ? `Ghế ${evt.seat_id < 10 ? '0' : ''}${evt.seat_id}`
                        : `ID ${evt.track_id < 10 ? '0' : ''}${evt.track_id}`}
                    </span>
                    {evt.reasons.join(', ')}
                  </span>
                  <span className="text-slate-400 text-[11px] font-mono flex items-center gap-1">
                    <Clock size={11} />
                    {new Date(evt.start_ms).toLocaleTimeString()}
                  </span>
                </div>

                {/* Duration & Peak metrics */}
                <div className="flex items-center gap-3 mt-2 text-[11px] text-slate-400">
                  <span>Thời lượng: <strong className="text-slate-200 font-mono">{(evt.duration_ms / 1000).toFixed(1)}s</strong></span>
                  {evt.max_yaw_delta !== undefined && (
                    <span>Max Yaw: <strong className="text-slate-200 font-mono">{evt.max_yaw_delta}°</strong></span>
                  )}
                  {evt.evidence_url && (
                    <button
                      type="button"
                      onClick={() => openEvidence(evt.evidence_url!, msg => setClipNotes(n => ({ ...n, [evt.event_id]: msg })))}
                      className="ml-auto px-2 py-0.5 rounded-md text-[11px] font-medium flex items-center gap-1 bg-sky-950/50 text-sky-300 hover:bg-sky-900/60 border border-sky-800/50 transition-all"
                      title="Xem clip bằng chứng 5 giây trước và sau sự kiện"
                    >
                      <Film size={12} />
                      <span>Clip</span>
                    </button>
                  )}
                </div>
                {clipNotes[evt.event_id] && (
                  <p className="mt-1.5 text-[11px] text-sky-300/80">{clipNotes[evt.event_id]}</p>
                )}

                {/* Supervisor Review Action Buttons */}
                <div className="flex items-center gap-1.5 mt-3 pt-2.5 border-t border-slate-800/60">
                  <button
                    type="button"
                    onClick={() => onUpdateStatus(evt.event_id, 'CONFIRMED')}
                    className={`flex-1 py-1 px-2 rounded-lg text-[11px] font-medium flex items-center justify-center gap-1 transition-all ${
                      isConfirmed
                        ? 'bg-rose-600 text-white'
                        : 'bg-rose-950/40 text-rose-300 hover:bg-rose-900/60 border border-rose-800/50'
                    }`}
                  >
                    <CheckCircle2 size={12} />
                    <span>Xác nhận</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => onUpdateStatus(evt.event_id, 'NEEDS_REVIEW')}
                    className={`flex-1 py-1 px-2 rounded-lg text-[11px] font-medium flex items-center justify-center gap-1 transition-all ${
                      isNeedsReview
                        ? 'bg-amber-600 text-white'
                        : 'bg-amber-950/40 text-amber-300 hover:bg-amber-900/60 border border-amber-800/50'
                    }`}
                  >
                    <Eye size={12} />
                    <span>Xem xét</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => onUpdateStatus(evt.event_id, 'DISMISSED')}
                    className={`flex-1 py-1 px-2 rounded-lg text-[11px] font-medium flex items-center justify-center gap-1 transition-all ${
                      isDismissed
                        ? 'bg-slate-700 text-white'
                        : 'bg-slate-800/60 text-slate-400 hover:bg-slate-700/60 border border-slate-700/60'
                    }`}
                  >
                    <XCircle size={12} />
                    <span>Bỏ qua</span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
