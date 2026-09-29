import React from 'react';
import { Camera, AlertCircle } from 'lucide-react';
import { TrackResult, CameraFacingMode } from '../../types/monitoring';
import { TrackOverlay } from './TrackOverlay';
import { CameraError } from '../../hooks/useCamera';

interface CameraViewProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isStreaming: boolean;
  facingMode: CameraFacingMode;
  tracks: TrackResult[];
  videoDimensions: { width: number; height: number };
  error: CameraError | null;
}

export const CameraView: React.FC<CameraViewProps> = ({
  videoRef,
  isStreaming,
  facingMode,
  tracks,
  videoDimensions,
  error
}) => {
  return (
    <div className="relative w-full aspect-[4/3] sm:aspect-[16/10] bg-slate-950 rounded-2xl overflow-hidden border border-slate-800/80 shadow-lg flex items-center justify-center">
      {/* Realtime Video Stream */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`w-full h-full object-contain ${
          facingMode === 'user' ? 'scale-x-[-1]' : ''
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

      {/* Idle / Unstarted Camera Placeholder */}
      {!isStreaming && (
        <div className="flex flex-col items-center justify-center gap-3 p-6 text-center text-slate-400">
          <div className="w-14 h-14 rounded-full bg-slate-900/80 border border-slate-700/60 flex items-center justify-center text-blue-400">
            <Camera size={28} />
          </div>
          <div>
            <h3 className="text-base font-medium text-slate-200">
              Camera Chưa Bật
            </h3>
            <p className="text-xs text-slate-400 mt-1 max-w-xs">
              Nhấn nút <strong>"Bắt đầu"</strong> bên dưới để cấp quyền và mở camera giám sát.
            </p>
          </div>
        </div>
      )}

      {/* Camera Error Message Banner */}
      {error && (
        <div className="absolute bottom-3 left-3 right-3 bg-rose-950/90 border border-rose-700/80 text-rose-200 text-xs rounded-xl p-3 flex items-start gap-2.5 backdrop-blur-md z-20">
          <AlertCircle size={16} className="text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold block">Lỗi Camera:</span>
            <span>{error.message}</span>
          </div>
        </div>
      )}
    </div>
  );
};
