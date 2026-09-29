import React from 'react';
import { ShieldAlert, Play, Square, SwitchCamera, Cpu, Radio, Settings2 } from 'lucide-react';
import { ConnectionStatus } from '../monitoring/ConnectionStatus';
import { SocketConnectionState, CameraFacingMode } from '../../types/monitoring';

interface HeaderProps {
  connectionState: SocketConnectionState;
  isStreaming: boolean;
  facingMode: CameraFacingMode;
  fps: number;
  latencyMs: number;
  useMock: boolean;
  onToggleMock: () => void;
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
  useMock,
  onToggleMock,
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
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-blue-500/15 border border-blue-500/30 text-blue-400 hidden xs:inline">
                AI Live
              </span>
            </h1>
            <p className="hidden sm:block text-[10px] text-slate-400 font-medium">
              Webcam AI • YOLOv8 • ByteTrack • MediaPipe
            </p>
          </div>
        </div>

        {/* Center: Mode Indicator & Connection State */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Fast Mode Toggle */}
          <button
            type="button"
            onClick={onToggleMock}
            className={`px-2 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border ${
              useMock
                ? 'bg-blue-950/40 text-blue-300 border-blue-800/60 hover:bg-blue-900/40'
                : 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/40'
            }`}
            title="Nhấn để chuyển nhanh giữa Mock Demo và Live WebSocket Backend"
          >
            {useMock ? <Cpu size={13} className="text-blue-400" /> : <Radio size={13} className="text-emerald-400" />}
            <span className="hidden md:inline">{useMock ? 'Mock Demo' : 'Live WebSocket'}</span>
            <span className="md:hidden">{useMock ? 'Mock' : 'Live'}</span>
          </button>

          <ConnectionStatus status={connectionState} fps={fps} latencyMs={latencyMs} />

          {/* AI / WebSocket Settings Button */}
          <button
            type="button"
            onClick={onOpenConfig}
            className="p-1.5 sm:px-2.5 sm:py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/80 text-xs font-medium flex items-center gap-1.5 transition-colors"
            title="Cài đặt kết nối Model AI & thông số Camera"
          >
            <Settings2 size={15} className="text-blue-400" />
            <span className="hidden sm:inline">Ghép Model</span>
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
              <span>Bắt đầu</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onStop}
              className="px-4 py-1.5 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 flex items-center gap-1.5 shadow-sm shadow-rose-600/20 transition-all active:scale-95"
            >
              <Square size={13} fill="currentColor" />
              <span>Dừng</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
