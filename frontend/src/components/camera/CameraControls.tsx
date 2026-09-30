import React, { useRef } from 'react';
import { Play, Square, SwitchCamera, Video, Gauge, Zap, Upload, Film } from 'lucide-react';
import { CameraFacingMode } from '../../types/monitoring';
import { VideoDevice } from '../../hooks/useCamera';

interface CameraControlsProps {
  isStreaming: boolean;
  isVideoFile?: boolean;
  facingMode: CameraFacingMode;
  activeDeviceId: string;
  availableDevices: VideoDevice[];
  targetFps?: number;
  onUpdateFps?: (fps: number) => void;
  onStart: () => void;
  onStop: () => void;
  onToggleCamera: () => void;
  onSelectDevice: (deviceId: string) => void;
  onSelectVideoFile?: (file: File) => void;
}

export const CameraControls: React.FC<CameraControlsProps> = ({
  isStreaming,
  isVideoFile = false,
  facingMode,
  activeDeviceId,
  availableDevices,
  targetFps = 10,
  onUpdateFps,
  onStart,
  onStop,
  onToggleCamera,
  onSelectDevice,
  onSelectVideoFile
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onSelectVideoFile) {
      onSelectVideoFile(file);
    }
    // Reset input so same file can be picked again
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="flex flex-col gap-3 w-full py-1">
      {/* Primary Touch Action Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 w-full">
        {/* Toggle Front / Back Camera Button */}
        <button
          type="button"
          onClick={onToggleCamera}
          disabled={!isStreaming || isVideoFile}
          className={`flex items-center justify-center gap-1.5 px-3 py-3 rounded-2xl text-xs sm:text-sm font-semibold transition-all select-none active:scale-[0.98] ${
            isStreaming && !isVideoFile
              ? 'bg-slate-900/90 text-slate-100 border border-slate-700/80 hover:bg-slate-800 shadow-md hover:border-slate-600'
              : 'bg-slate-950/40 text-slate-600 border border-slate-800/40 cursor-not-allowed'
          }`}
          title={`Đổi sang camera ${facingMode === 'environment' ? 'trước' : 'sau'}`}
        >
          <SwitchCamera size={16} className={isStreaming && !isVideoFile ? 'text-cyan-400' : 'text-slate-600'} />
          <span className="truncate">
            {facingMode === 'environment' ? 'Cam Trước' : 'Cam Sau'}
          </span>
        </button>

        {/* Upload Video Test Button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center justify-center gap-1.5 px-3 py-3 rounded-2xl text-xs sm:text-sm font-semibold bg-slate-900/90 text-slate-100 border border-indigo-700/60 hover:border-indigo-500 hover:bg-indigo-950/40 transition-all select-none active:scale-[0.98] shadow-md shadow-indigo-950/40"
          title="Tải video từ máy tính hoặc điện thoại để AI nhận diện thử"
        >
          <input 
            ref={fileInputRef} 
            type="file" 
            accept="video/*" 
            onChange={handleFileChange} 
            className="hidden" 
          />
          {isVideoFile ? (
            <>
              <Film size={16} className="text-purple-400 animate-pulse" />
              <span className="truncate text-purple-200">Đang Phát Video</span>
            </>
          ) : (
            <>
              <Upload size={16} className="text-indigo-400" />
              <span className="truncate">Tải Video Test</span>
            </>
          )}
        </button>

        {/* Start / Stop Main Action Button */}
        {!isStreaming ? (
          <button
            type="button"
            onClick={onStart}
            className="col-span-2 sm:col-span-1 flex items-center justify-center gap-2 px-4 py-3 rounded-2xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-[0.98] shadow-lg shadow-blue-600/30 transition-all select-none"
          >
            <Play size={16} fill="currentColor" />
            <span>Bật Camera</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={onStop}
            className="col-span-2 sm:col-span-1 flex items-center justify-center gap-2 px-4 py-3 rounded-2xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 active:scale-[0.98] shadow-lg shadow-rose-600/30 transition-all select-none"
          >
            <Square size={16} fill="currentColor" />
            <span>Dừng {isVideoFile ? 'Video' : 'Camera'}</span>
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
        {!isVideoFile && availableDevices.length > 2 && (
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
          <span>YOLOv8n + SolvePnP + v2 Suspicion</span>
        </div>
      </div>
    </div>
  );
};
