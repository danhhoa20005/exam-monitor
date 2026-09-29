import React from 'react';
import { ShieldAlert, Play, Square, SwitchCamera, Radio, Settings2 } from 'lucide-react';
import { ConnectionStatus } from '../monitoring/ConnectionStatus';
import { SocketConnectionState, CameraFacingMode } from '../../types/monitoring';

interface HeaderProps {
  connectionState: SocketConnectionState;
  isStreaming: boolean;
  facingMode: CameraFacingMode;
  fps: number;
  latencyMs: number;
  onStart: () => void;
  onStop: () => void;
  onToggleCamera: () => void;
  onOpenConfig: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  connectionState,
  isStreaming,
  facingMode,
  fps,
  latencyMs,
  onStart,
  onStop,
  onToggleCamera,
  onOpenConfig
}) => {
  return (
    <header className="w-full bg-slate-900/90 border-b border-slate-800/80 backdrop-blur-md sticky top-0 z-30 px-3 py-2.5 sm:px-4 sm:py-3 md:px-6">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-2 sm:gap-4">
        
        {/* Left: Brand / Logo */}
        <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
          <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 shrink-0">
            <ShieldAlert size={18} />
          </div>
          <div>
            <h1 className="text-xs sm:text-base font-bold text-slate-100 tracking-tight leading-tight flex items-center gap-1.5">
              <span>Giám Sát Tư Thế</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 flex items-center gap-1">
                <Radio size={10} className="animate-pulse text-emerald-400" />
                <span>AI Live Model</span>
              </span>
            </h1>
            <p className="hidden sm:block text-[10px] text-slate-400 font-medium">
              YOLOv8m (`best.pt`) • ByteTrack • MediaPipe Pose
            </p>
          </div>
        </div>

        {/* Center: Live Connection State & FPS */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          <ConnectionStatus status={connectionState} fps={fps} latencyMs={latencyMs} />

          {/* AI / WebSocket Settings Button */}
          <button
            type="button"
            onClick={onOpenConfig}
            className="p-1.5 sm:px-2.5 sm:py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/80 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
            title="Cài đặt kết nối WebSocket AI Model Backend"
          >
            <Settings2 size={15} className="text-blue-400" />
            <span className="hidden sm:inline">Cài Đặt Model</span>
          </button>
        </div>

        {/* Right: Quick Action Controls */}
        <div className="hidden md:flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={onToggleCamera}
            disabled={!isStreaming}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
              isStreaming
                ? 'bg-slate-800 text-slate-200 hover:bg-slate-700 border border-slate-700'
                : 'bg-slate-900/40 text-slate-600 border border-slate-800/60 cursor-not-allowed'
            }`}
            title={`Đang dùng camera ${facingMode === 'environment' ? 'sau' : 'trước'}`}
          >
            <SwitchCamera size={14} className={isStreaming ? 'text-blue-400' : 'text-slate-600'} />
            <span>{facingMode === 'environment' ? 'Cam Sau' : 'Cam Trước'}</span>
          </button>

          {!isStreaming ? (
            <button
              type="button"
              onClick={onStart}
              className="px-4 py-1.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 flex items-center gap-1.5 shadow-sm shadow-blue-600/20 transition-all active:scale-95"
            >
              <Play size={13} fill="currentColor" />
              <span>Mở Camera</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onStop}
              className="px-4 py-1.5 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 flex items-center gap-1.5 shadow-sm shadow-rose-600/20 transition-all active:scale-95"
            >
              <Square size={13} fill="currentColor" />
              <span>Dừng Camera</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
