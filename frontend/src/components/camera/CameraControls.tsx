import React from 'react';
import { Play, Square, SwitchCamera } from 'lucide-react';
import { CameraFacingMode } from '../../types/monitoring';

interface CameraControlsProps {
  isStreaming: boolean;
  facingMode: CameraFacingMode;
  onStart: () => void;
  onStop: () => void;
  onToggleCamera: () => void;
}

export const CameraControls: React.FC<CameraControlsProps> = ({
  isStreaming,
  facingMode,
  onStart,
  onStop,
  onToggleCamera
}) => {
  return (
    <div className="flex items-center justify-center gap-3 w-full py-2">
      {/* Switch Camera Button (Front / Back) */}
      <button
        type="button"
        onClick={onToggleCamera}
        disabled={!isStreaming}
        className={`flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold transition-all select-none active:scale-95 ${
          isStreaming
            ? 'bg-slate-800/90 text-slate-200 border border-slate-700/80 hover:bg-slate-700 hover:text-white shadow-sm'
            : 'bg-slate-900/40 text-slate-600 border border-slate-800 cursor-not-allowed'
        }`}
        title={`Đang dùng camera ${facingMode === 'environment' ? 'sau' : 'trước'}`}
      >
        <SwitchCamera size={18} className={isStreaming ? 'text-blue-400' : 'text-slate-600'} />
        <span>Đổi cam ({facingMode === 'environment' ? 'Sau' : 'Trước'})</span>
      </button>

      {/* Start / Stop Camera Action Button */}
      {!isStreaming ? (
        <button
          type="button"
          onClick={onStart}
          className="flex-1 max-w-[200px] flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 active:scale-95 shadow-md shadow-blue-600/20 transition-all select-none"
        >
          <Play size={18} fill="currentColor" />
          <span>Bắt đầu</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={onStop}
          className="flex-1 max-w-[200px] flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white bg-rose-600 hover:bg-rose-500 active:scale-95 shadow-md shadow-rose-600/20 transition-all select-none"
        >
          <Square size={18} fill="currentColor" />
          <span>Dừng</span>
        </button>
      )}
    </div>
  );
};
