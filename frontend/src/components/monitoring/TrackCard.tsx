import React from 'react';
import { TrackResult } from '../../types/monitoring';
import { STATUS_STYLES, STATUS_LABELS } from '../../constants/config';
import { RotateCw, ArrowDown, User, Hand, Eye, AlertTriangle, ShieldAlert } from 'lucide-react';

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
  const suspicionScore = track.suspicion_score ?? 0;
  const suspicionLevel = track.suspicion_level || 'NORMAL';

  // Suspicion level badge color
  const levelBadge = {
    ALERT: 'bg-rose-500/25 text-rose-300 border-rose-500/50 shadow-rose-900/50 shadow-sm animate-pulse',
    WARNING: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
    ATTENTION: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    NORMAL: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  }[suspicionLevel] || 'bg-slate-800 text-slate-300 border-slate-700';

  // Progress bar color
  const barGradient = suspicionScore >= 80 
    ? 'from-rose-600 to-red-500' 
    : suspicionScore >= 60 
      ? 'from-amber-500 to-orange-500' 
      : suspicionScore >= 30 
        ? 'from-blue-500 to-amber-400' 
        : 'from-emerald-500 to-teal-400';

  return (
    <div 
      className={`p-3.5 rounded-xl border transition-all duration-200 ${
        isReview || suspicionLevel === 'ALERT'
          ? 'bg-rose-950/30 border-rose-600/60 shadow-sm shadow-rose-950' 
          : suspicionLevel === 'WARNING'
            ? 'bg-amber-950/20 border-amber-500/50'
            : activity === 'hand_raised'
              ? 'bg-blue-950/30 border-blue-500/60 shadow-sm shadow-blue-950'
              : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
      }`}
    >
      {/* Top row: ID & Status Badge */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700/60 flex items-center justify-center text-slate-300 text-xs font-semibold">
            <User size={14} className={isReview || suspicionLevel === 'ALERT' ? 'text-rose-400' : 'text-blue-400'} />
          </div>
          <span className="text-sm font-semibold text-slate-100">
            ID {track.track_id < 10 ? '0' : ''}{track.track_id}
          </span>
        </div>

        <span className={`px-2.5 py-1 rounded-md text-[11px] font-medium border ${style.badgeBg} ${style.badgeText} ${style.borderColor}`}>
          {statusDetail}
        </span>
      </div>

      {/* v2 Suspicion Meter (0-100) */}
      {!isCalib && track.status !== 'POSE_UNAVAILABLE' && (
        <div className="mt-3 bg-slate-950/70 p-2.5 rounded-lg border border-slate-800/80">
          <div className="flex items-center justify-between text-[11px] mb-1.5">
            <div className="flex items-center gap-1.5 text-slate-400">
              <ShieldAlert size={12} className={suspicionScore >= 60 ? 'text-rose-400' : 'text-slate-400'} />
              <span>Chỉ số nghi vấn:</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${levelBadge}`}>
                {suspicionLevel}
              </span>
              <strong className="text-slate-200 font-mono">{suspicionScore}/100</strong>
            </div>
          </div>
          {/* Progress bar */}
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div 
              className={`h-full bg-gradient-to-r ${barGradient} transition-all duration-300`} 
              style={{ width: `${Math.max(5, suspicionScore)}%` }}
            />
          </div>
        </div>
      )}

      {/* Activity Classification Badges (from YOLOv8n + v2 Signals) */}
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        {activity === 'hand_raised' && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/40 animate-pulse">
            <Hand size={11} className="text-sky-400" />
            Giơ tay phát biểu
          </span>
        )}
        {activity === 'inattentive' && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/40">
            <AlertTriangle size={11} className="text-rose-400" />
            Mất tập trung
          </span>
        )}
        {activity === 'attentive' && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            <Eye size={11} className="text-emerald-400" />
            Tập trung làm bài
          </span>
        )}
        {track.is_leaning && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            Nghiêng người
          </span>
        )}
        {(track.turn_count_10s ?? 0) >= 3 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/40">
            Quay {track.turn_count_10s} lần/10s
          </span>
        )}
      </div>

      {/* Metric details row (if calibrated) */}
      {!isCalib && track.status !== 'POSE_UNAVAILABLE' && (
        <div className="grid grid-cols-2 gap-2 mt-2.5 pt-2 border-t border-slate-800/60 text-xs text-slate-400">
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
        <div className="mt-2 flex items-center gap-1 text-[11px] text-slate-400">
          <span className="text-slate-500">Lý do:</span>
          <span className="font-medium text-slate-300">{track.reasons.join(', ')}</span>
        </div>
      )}
    </div>
  );
};
