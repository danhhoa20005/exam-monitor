import React from 'react';
import { Play, Square, SwitchCamera, Video, Gauge, Zap } from 'lucide-react';
import { CameraFacingMode } from '../../types/monitoring';
import { VideoDevice } from '../../hooks/useCamera';

interface CameraControlsProps {
  isStreaming: boolean;
  facingMode: CameraFacingMode;
  activeDeviceId: string;
  availableDevices: VideoDevice[];
  targetFps?: number;
  onUpdateFps?: (fps: number) => void;
  onStart: () => void;
  onStop: () => void;
  onToggleCamera: () => void;
  onSelectDevice: (deviceId: string) => void;
}

export const CameraControls: React.FC<CameraControlsProps> = ({
  isStreaming,
  facingMode,
  activeDeviceId,
  availableDevices,
  targetFps = 10,
  onUpdateFps,
  onStart,
  onStop,
  onToggleCamera,
  onSelectDevice
}) => {
  return (
    <div className="flex flex-col gap-3 w-full py-1">
      {/* Primary Touch Action Bar */}
      <div className="grid grid-cols-2 gap-3 w-full">
        {/* Toggle Front / Back Camera Button */}
        <button
          type="button"
          onClick={onToggleCamera}
          disabled={!isStreaming}
          className={`flex items-center justify-center gap-2 px-4 py-3.5 rounded-2xl text-xs sm:text-sm font-semibold transition-all select-none active:scale-[0.98] ${
            isStreaming
              ? 'bg-slate-900/90 text-slate-100 border border-slate-700/80 hover:bg-slate-800 shadow-md hover:border-slate-600'
              : 'bg-slate-950/40 text-slate-600 border border-slate-800/40 cursor-not-allowed'
          }`}
          title={`Đổi sang camera ${facingMode === 'environment' ? 'trước' : 'sau'}`}
        >
          <SwitchCamera size={18} className={isStreaming ? 'text-cyan-400' : 'text-slate-600'} />
          <span className="truncate">
            {facingMode === 'environment' ? 'Chuyển: Cam Trước' : 'Chuyển: Cam Sau'}
          </span>
        </button>

        {/* Start / Stop Main Action Button */}
        {!isStreaming ? (
          <button
            type="button"
            onClick={onStart}
            className="flex items-center justify-center gap-2 px-5 py-3.5 rounded-2xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-[0.98] shadow-lg shadow-blue-600/30 transition-all select-none"
          >
            <Play size={18} fill="currentColor" />
            <span>Bắt Đầu Giám Sát</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={onStop}
            className="flex items-center justify-center gap-2 px-5 py-3.5 rounded-2xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 active:scale-[0.98] shadow-lg shadow-rose-600/30 transition-all select-none"
          >
            <Square size={18} fill="currentColor" />
            <span>Dừng Giám Sát</span>
          </button>
        )}
      </div>

      {/* Quick Performance & Hardware Settings Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 bg-slate-900/60 border border-slate-800/80 rounded-2xl p-2.5 sm:px-4 text-xs">
        {/* Left: FPS Profile Switcher */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-semibold">
            <Gauge size={14} className="text-cyan-400 shrink-0" />
            <span>Tốc độ FPS:</span>
          </div>

          <div className="inline-flex rounded-xl bg-slate-950 p-1 border border-slate-800 text-[11px]">
            {[
              { fps: 5, label: '5 FPS' },
              { fps: 10, label: '10 FPS' },
              { fps: 15, label: '15 FPS' }
            ].map(item => (
              <button
                key={item.fps}
                type="button"
                onClick={() => onUpdateFps && onUpdateFps(item.fps)}
                className={`px-2.5 py-1 rounded-lg font-mono font-bold transition-all ${
                  targetFps === item.fps
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/50'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Right: Camera Eye Selector (If multi-camera) */}
        {availableDevices.length > 2 && (
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Video size={13} className="text-blue-400 shrink-0" />
            <select
              value={activeDeviceId}
              onChange={(e) => onSelectDevice(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 outline-none cursor-pointer truncate max-w-[140px] font-mono"
            >
              {availableDevices.map(d => (
                <option key={d.deviceId} value={d.deviceId}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Status Hint */}
        <div className="hidden sm:flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
          <Zap size={12} className="text-emerald-400" />
          <span>YOLOv8 + SolvePnP 3D Euler</span>
        </div>
      </div>
    </div>
  );
};
