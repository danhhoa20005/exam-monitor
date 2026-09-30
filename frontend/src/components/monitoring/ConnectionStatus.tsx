import React from 'react';
import { SocketConnectionState } from '../../types/monitoring';
import { Activity } from 'lucide-react';

interface ConnectionStatusProps {
  status: SocketConnectionState;
  fps?: number;
  latencyMs?: number;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  status,
  fps = 0,
  latencyMs = 0
}) => {
  let label = 'Chưa kết nối AI';
  let dotColor = 'bg-slate-500';
  let badgeBorder = 'border-slate-800 bg-slate-900/80 text-slate-300';

  if (status === 'connected') {
    label = 'Live AI Connected';
    dotColor = 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]';
    badgeBorder = 'border-emerald-500/40 bg-emerald-950/40 text-emerald-300 shadow-sm shadow-emerald-950';
  } else if (status === 'connecting' || status === 'reconnecting') {
    label = status === 'connecting' ? 'Đang kết nối AI...' : 'Đang thử lại...';
    dotColor = 'bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(251,191,36,0.8)]';
    badgeBorder = 'border-amber-500/40 bg-amber-950/40 text-amber-300';
  } else if (status === 'error') {
    label = 'Lỗi kết nối';
    dotColor = 'bg-rose-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]';
    badgeBorder = 'border-rose-500/40 bg-rose-950/40 text-rose-300';
  }

  const fpsColor = fps >= 10 ? 'text-emerald-400' : fps >= 5 ? 'text-cyan-400' : 'text-amber-400';

  return (
    <div className="flex items-center gap-1.5 sm:gap-2">
      {/* Main Connection Status Pill */}
      <div className={`inline-flex items-center gap-1.5 sm:gap-2 px-2.5 py-1 rounded-full text-[11px] sm:text-xs font-semibold border backdrop-blur-md transition-colors ${badgeBorder}`}>
        <span className={`w-2 h-2 rounded-full ${dotColor}`} />
        <span className="truncate max-w-[110px] sm:max-w-none">{label}</span>
      </div>

      {/* Live Telemetry Pill: FPS & Latency (Visible on all devices) */}
      {status === 'connected' && (
        <div className="inline-flex items-center gap-1 text-[11px] font-mono font-bold bg-slate-900/90 border border-slate-700/80 px-2 py-0.5 rounded-lg text-slate-300 shadow-inner">
          <Activity size={11} className={`${fpsColor} shrink-0 animate-pulse`} />
          <span className={fpsColor}>{fps > 0 ? fps : '--'} FPS</span>
          {latencyMs > 0 && (
            <span className="hidden xs:inline text-[10px] text-slate-400">
              • {latencyMs}ms
            </span>
          )}
        </div>
      )}
    </div>
  );
};
