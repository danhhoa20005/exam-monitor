import React from 'react';
import { MonitoringEvent, EventReviewStatus } from '../../types/monitoring';
import { AlertTriangle, CheckCircle2, Eye, XCircle, Clock, Download, FileSpreadsheet } from 'lucide-react';

interface EventPanelProps {
  events: MonitoringEvent[];
  onUpdateStatus: (eventId: string, status: EventReviewStatus) => void;
  onExportCsv: () => void;
  onExportJson: () => void;
}

export const EventPanel: React.FC<EventPanelProps> = ({
  events,
  onUpdateStatus,
  onExportCsv,
  onExportJson
}) => {
  return (
    <div className="flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle size={18} className="text-amber-400" />
          <h2 className="text-sm font-semibold text-slate-100">
            Nhật Ký Sự Kiện Nghi Vấn ({events.length})
          </h2>
        </div>

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
          </div>
        )}
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
                      ID {evt.track_id < 10 ? '0' : ''}{evt.track_id}
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
                </div>

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
