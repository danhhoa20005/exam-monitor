import React from 'react';
import { Play, Square, SwitchCamera, Video } from 'lucide-react';
import { CameraFacingMode } from '../../types/monitoring';
import { VideoDevice } from '../../hooks/useCamera';

interface CameraControlsProps {
  isStreaming: boolean;
  facingMode: CameraFacingMode;
  activeDeviceId: string;
  availableDevices: VideoDevice[];
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
  onStart,
  onStop,
  onToggleCamera,
  onSelectDevice
}) => {
  return (
    <div className="flex flex-col gap-2.5 w-full py-1">
      {/* Primary Touch Action Bar */}
      <div className="grid grid-cols-2 gap-3 w-full">
        {/* Toggle Front / Back Camera Button */}
        <button
          type="button"
          onClick={onToggleCamera}
          disabled={!isStreaming}
          className={`flex items-center justify-center gap-2 px-4 py-3.5 rounded-xl text-xs sm:text-sm font-semibold transition-all select-none active:scale-[0.98] ${
            isStreaming
              ? 'bg-slate-800/90 text-slate-100 border border-slate-700/80 hover:bg-slate-700 shadow-md'
              : 'bg-slate-900/40 text-slate-600 border border-slate-800/60 cursor-not-allowed'
          }`}
          title={`Đổi sang camera ${facingMode === 'environment' ? 'trước (selfie)' : 'sau (môi trường)'}`}
        >
          <SwitchCamera size={18} className={isStreaming ? 'text-blue-400' : 'text-slate-600'} />
          <span className="truncate">
            {facingMode === 'environment' ? 'Chuyển: Cam Trước' : 'Chuyển: Cam Sau'}
          </span>
        </button>

        {/* Start / Stop Main Action Button */}
        {!isStreaming ? (
          <button
            type="button"
            onClick={onStart}
            className="flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-xs sm:text-sm font-bold text-white bg-blue-600 hover:bg-blue-500 active:scale-[0.98] shadow-lg shadow-blue-600/25 transition-all select-none"
          >
            <Play size={18} fill="currentColor" />
            <span>Mở Camera</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={onStop}
            className="flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-xs sm:text-sm font-bold text-white bg-rose-600 hover:bg-rose-500 active:scale-[0.98] shadow-lg shadow-rose-600/25 transition-all select-none"
          >
            <Square size={18} fill="currentColor" />
            <span>Dừng Camera</span>
          </button>
        )}
      </div>

      {/* Optional Camera Device Dropdown (If device has multiple cameras e.g. Wide / Ultra-wide / External) */}
      {isStreaming && availableDevices.length > 2 && (
        <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800/90 rounded-xl px-3 py-2 text-xs text-slate-400">
          <Video size={14} className="text-blue-400 shrink-0" />
          <span className="shrink-0 text-slate-300 font-medium">Chọn mắt cam:</span>
          <select
            value={activeDeviceId}
            onChange={(e) => onSelectDevice(e.target.value)}
            className="flex-1 bg-transparent text-slate-200 outline-none cursor-pointer truncate text-xs font-mono"
          >
            {availableDevices.map(d => (
              <option key={d.deviceId} value={d.deviceId} className="bg-slate-900 text-slate-200">
                {d.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};
