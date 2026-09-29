import React from 'react';
import { SocketConnectionState } from '../../types/monitoring';
import { USE_MOCK_DATA } from '../../constants/config';

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
  let label = 'Chưa kết nối';
  let dotColor = 'bg-slate-500';
  let badgeBorder = 'border-slate-700/60 bg-slate-900/60 text-slate-300';

  if (status === 'connected') {
    label = USE_MOCK_DATA ? 'Chế độ Demo (Mock)' : 'Đã kết nối AI';
    dotColor = 'bg-emerald-400 shadow-sm shadow-emerald-400/50';
    badgeBorder = 'border-emerald-500/30 bg-emerald-950/40 text-emerald-300';
  } else if (status === 'connecting' || status === 'reconnecting') {
    label = status === 'connecting' ? 'Đang kết nối...' : 'Đang kết nối lại...';
    dotColor = 'bg-amber-400 animate-pulse';
    badgeBorder = 'border-amber-500/30 bg-amber-950/40 text-amber-300';
  } else if (status === 'error') {
    label = 'Lỗi kết nối AI';
    dotColor = 'bg-rose-400';
    badgeBorder = 'border-rose-500/30 bg-rose-950/40 text-rose-300';
  }

  return (
    <div className="flex items-center gap-2">
      <div className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium border backdrop-blur-md ${badgeBorder}`}>
        <span className={`w-2 h-2 rounded-full ${dotColor}`} />
        <span>{label}</span>
      </div>

      {status === 'connected' && fps > 0 && (
        <span className="hidden sm:inline-block text-[11px] font-mono text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded-md border border-slate-700/40">
          {fps} FPS {latencyMs > 0 ? `• ${latencyMs}ms` : ''}
        </span>
      )}
    </div>
  );
};
