import React from 'react';
import { TrackResult } from '../../types/monitoring';
import { STATUS_STYLES, STATUS_LABELS } from '../../constants/config';
import { RotateCw, ArrowDown, User, Hand, Eye, AlertTriangle } from 'lucide-react';

interface TrackCardProps {
  track: TrackResult;
}

export const TrackCard: React.FC<TrackCardProps> = ({ track }) => {
  const style = STATUS_STYLES[track.status] || STATUS_STYLES.POSE_UNAVAILABLE;
  const isReview = track.status === 'REVIEW';
  const isObserving = track.status === 'OBSERVING';
  const isCalib = track.status === 'CALIBRATING';

  let statusDetail = STATUS_LABELS[track.status];
  if (isCalib) {
    statusDetail = `Lấy mốc ${track.calibration_samples}/20`;
  } else if (isObserving && track.turning_duration_ms) {
    const s = (track.turning_duration_ms / 1000).toFixed(1);
    statusDetail = `Đang theo dõi (${s}s)`;
  } else if (isReview && track.turning_duration_ms) {
    const s = (track.turning_duration_ms / 1000).toFixed(1);
    statusDetail = `Nghi vấn (${s}s)`;
  }

  const activity = track.activity || 'attentive';

  return (
    <div 
      className={`p-3.5 rounded-xl border transition-all duration-200 ${
        isReview || activity === 'inattentive'
          ? 'bg-rose-950/30 border-rose-600/60 shadow-sm shadow-rose-950' 
          : activity === 'hand_raised'
            ? 'bg-blue-950/30 border-blue-500/60 shadow-sm shadow-blue-950'
            : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
      }`}
    >
      {/* Top row: ID & Status Badge */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700/60 flex items-center justify-center text-slate-300 text-xs font-semibold">
            <User size={14} className={isReview ? 'text-rose-400' : 'text-blue-400'} />
          </div>
          <span className="text-sm font-semibold text-slate-100">
            ID {track.track_id < 10 ? '0' : ''}{track.track_id}
          </span>
        </div>

        <span className={`px-2.5 py-1 rounded-md text-[11px] font-medium border ${style.badgeBg} ${style.badgeText} ${style.borderColor}`}>
          {statusDetail}
        </span>
      </div>

      {/* Activity Classification Badge (from YOLOv8n) */}
      <div className="mt-2.5 flex items-center gap-2">
        {activity === 'hand_raised' && (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/40 animate-pulse">
            <Hand size={12} className="text-sky-400" />
            Giơ tay (Hand Raised)
          </span>
        )}
        {activity === 'inattentive' && (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/40">
            <AlertTriangle size={12} className="text-rose-400" />
            Mất tập trung (Inattentive)
          </span>
        )}
        {activity === 'attentive' && (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            <Eye size={12} className="text-emerald-400" />
            Tập trung (Attentive)
          </span>
        )}
      </div>

      {/* Metric details row (if calibrated) */}
      {!isCalib && track.status !== 'POSE_UNAVAILABLE' && (
        <div className="grid grid-cols-2 gap-2 mt-3 pt-2.5 border-t border-slate-800/60 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <RotateCw size={12} className={Math.abs(track.yaw_delta_deg || 0) > 35 ? 'text-rose-400' : 'text-slate-500'} />
            <span>Lệch Yaw:</span>
            <strong className="text-slate-200 font-mono">
              {(track.yaw_delta_deg || 0) > 0 ? `+${track.yaw_delta_deg}` : track.yaw_delta_deg}°
            </strong>
          </div>

          <div className="flex items-center gap-1.5">
            <ArrowDown size={12} className={(track.nose_drop_ratio || 0) > 0.15 ? 'text-rose-400' : 'text-slate-500'} />
            <span>Hạ mũi:</span>
            <strong className="text-slate-200 font-mono">
              {((track.nose_drop_ratio || 0) * 100).toFixed(0)}%
            </strong>
          </div>
        </div>
      )}

      {/* Reason Pill if any */}
      {track.reasons.length > 0 && (
        <div className="mt-2.5 flex items-center gap-1 text-[11px] text-slate-400">
          <span className="text-slate-500">Lý do:</span>
          <span className="font-medium text-slate-300">{track.reasons.join(', ')}</span>
        </div>
      )}
    </div>
  );
};
