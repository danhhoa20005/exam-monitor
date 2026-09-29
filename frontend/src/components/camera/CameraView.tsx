import React from 'react';
import { Camera, AlertCircle, RefreshCw } from 'lucide-react';
import { TrackResult, CameraFacingMode } from '../../types/monitoring';
import { TrackOverlay } from './TrackOverlay';
import { CameraError } from '../../hooks/useCamera';

interface CameraViewProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isStreaming: boolean;
  facingMode: CameraFacingMode;
  activeCameraLabel: string;
  tracks: TrackResult[];
  videoDimensions: { width: number; height: number };
  error: CameraError | null;
  onRetry?: () => void;
}

export const CameraView: React.FC<CameraViewProps> = ({
  videoRef,
  isStreaming,
  facingMode,
  activeCameraLabel,
  tracks,
  videoDimensions,
  error,
  onRetry
}) => {
  const isFrontCamera = facingMode === 'user';

  return (
    <div className="relative w-full aspect-[4/3] sm:aspect-[16/10] bg-slate-950 rounded-2xl overflow-hidden border border-slate-800/90 shadow-2xl flex items-center justify-center">
      {/* Realtime Video Stream */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`w-full h-full object-contain transition-transform duration-200 ${
          isFrontCamera ? 'scale-x-[-1]' : ''
        }`}
        style={{ display: isStreaming ? 'block' : 'none' }}
      />

      {/* Canvas Bounding Box & Status Overlay */}
      {isStreaming && (
        <TrackOverlay
          tracks={tracks}
          videoDimensions={videoDimensions}
          facingMode={facingMode}
        />
      )}

      {/* Camera Live Status Badge (Top-Left HUD) */}
      {isStreaming && (
        <div className="absolute top-3 left-3 flex flex-wrap items-center gap-1.5 sm:gap-2 z-20 pointer-events-none">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900/85 border border-slate-700/80 text-[11px] font-semibold text-slate-200 backdrop-blur-md shadow-lg">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse shadow-sm shadow-rose-500" />
            <span className="truncate max-w-[200px] sm:max-w-[280px]">
              LIVE • {activeCameraLabel}
            </span>
          </div>

          {videoDimensions.width > 0 && (
            <span className="hidden sm:inline-block px-2 py-1 rounded-md bg-slate-900/80 border border-slate-800 text-[10px] font-mono text-slate-300 backdrop-blur-md">
              {videoDimensions.width} × {videoDimensions.height}
            </span>
          )}

          {isFrontCamera && (
            <span className="px-2 py-1 rounded-md bg-blue-950/80 border border-blue-800/80 text-[10px] font-medium text-blue-300 backdrop-blur-md">
              Gương (Lật ngang)
            </span>
          )}
        </div>
      )}

      {/* Idle / Unstarted Camera Placeholder */}
      {!isStreaming && !error && (
        <div className="flex flex-col items-center justify-center gap-3.5 p-6 text-center text-slate-400 max-w-sm">
          <div className="w-14 h-14 rounded-2xl bg-slate-900/90 border border-slate-700/80 flex items-center justify-center text-blue-400 shadow-inner">
            <Camera size={28} />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-100">
              Camera Chưa Kích Hoạt
            </h3>
            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
              Mặc định ưu tiên <strong>Camera sau</strong> của điện thoại để bao quát phòng thi. Bạn có thể đổi sang <strong>Camera trước</strong> bất kỳ lúc nào.
            </p>
          </div>
        </div>
      )}

      {/* Camera Error Message Banner */}
      {error && (
        <div className="absolute inset-4 m-auto h-fit bg-rose-950/95 border border-rose-700 text-rose-200 text-xs rounded-2xl p-4 flex flex-col gap-3 backdrop-blur-md z-20 shadow-2xl max-w-md">
          <div className="flex items-start gap-2.5">
            <AlertCircle size={18} className="text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="font-bold block text-rose-100 mb-1">Không thể mở camera:</span>
              <p className="text-slate-200 leading-relaxed">{error.message}</p>
            </div>
          </div>
          {onRetry && (
            <div className="flex justify-end">
              <button
                type="button"
                onClick={onRetry}
                className="px-3 py-1.5 rounded-lg bg-rose-800 hover:bg-rose-700 text-white font-semibold text-xs flex items-center gap-1.5 transition-colors"
              >
                <RefreshCw size={12} />
                <span>Thử lại</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
