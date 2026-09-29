import React from 'react';
import { ShieldAlert, Play, Square, SwitchCamera } from 'lucide-react';
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
}

export const Header: React.FC<HeaderProps> = ({
  connectionState,
  isStreaming,
  facingMode,
  fps,
  latencyMs,
  onStart,
  onStop,
  onToggleCamera
}) => {
  return (
    <header className="w-full bg-slate-900/90 border-b border-slate-800/80 backdrop-blur-md sticky top-0 z-30 px-4 py-3 md:px-6">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        {/* Left: Brand / Title */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 shrink-0">
            <ShieldAlert size={20} />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-100 tracking-tight leading-tight">
              Giám Sát Tư Thế Realtime
            </h1>
            <p className="text-[11px] text-slate-400 font-medium">
              Webcam AI • YOLOv8 • ByteTrack • MediaPipe
            </p>
          </div>
        </div>

        {/* Center: Connection Status Pill */}
        <div className="hidden sm:flex items-center">
          <ConnectionStatus status={connectionState} fps={fps} latencyMs={latencyMs} />
        </div>

        {/* Right: Desktop Action Controls */}
        <div className="flex items-center gap-2">
          {/* Mobile status indicator */}
          <div className="sm:hidden">
            <ConnectionStatus status={connectionState} fps={fps} latencyMs={latencyMs} />
          </div>

          {/* Desktop Only: Switch Camera, Start/Stop quick triggers */}
          <div className="hidden md:flex items-center gap-2">
            <button
              type="button"
              onClick={onToggleCamera}
              disabled={!isStreaming}
              className={`p-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
                isStreaming
                  ? 'bg-slate-800 text-slate-200 hover:bg-slate-700 border border-slate-700'
                  : 'bg-slate-900/40 text-slate-600 border border-slate-800/60 cursor-not-allowed'
              }`}
              title={`Camera ${facingMode === 'environment' ? 'sau' : 'trước'}`}
            >
              <SwitchCamera size={16} />
              <span>{facingMode === 'environment' ? 'Cam Sau' : 'Cam Trước'}</span>
            </button>

            {!isStreaming ? (
              <button
                type="button"
                onClick={onStart}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 flex items-center gap-1.5 shadow-sm shadow-blue-600/20 transition-all"
              >
                <Play size={14} fill="currentColor" />
                <span>Bắt đầu</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onStop}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 flex items-center gap-1.5 shadow-sm shadow-rose-600/20 transition-all"
              >
                <Square size={14} fill="currentColor" />
                <span>Dừng</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
