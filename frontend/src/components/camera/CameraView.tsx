import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Camera, 
  AlertCircle, 
  RefreshCw, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Minimize2, 
  Eye, 
  EyeOff, 
  RotateCcw,
  AlertTriangle
} from 'lucide-react';
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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [showOverlay, setShowOverlay] = useState<boolean>(true);

  const isFrontCamera = facingMode === 'user';
  const reviewTracks = tracks.filter(t => t.status === 'REVIEW');

  // Handle Fullscreen toggle
  const handleToggleFullscreen = useCallback(async () => {
    const container = containerRef.current;
    if (!container) return;

    try {
      if (!document.fullscreenElement) {
        if (container.requestFullscreen) {
          await container.requestFullscreen();
        } else if ((container as any).webkitRequestFullscreen) {
          await (container as any).webkitRequestFullscreen();
        }
        setIsFullscreen(true);
      } else {
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if ((document as any).webkitExitFullscreen) {
          await (document as any).webkitExitFullscreen();
        }
        setIsFullscreen(false);
      }
    } catch (err) {
      console.warn('Fullscreen request failed, using CSS fallback:', err);
      setIsFullscreen(prev => !prev);
    }
  }, []);

  // Listen to browser fullscreen changes (e.g. user pressing ESC key)
  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    document.addEventListener('webkitfullscreenchange', onFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', onFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', onFullscreenChange);
    };
  }, []);

  // Zoom In / Out Handlers
  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(3.0, Number((prev + 0.25).toFixed(2))));
  };

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(1.0, Number((prev - 0.25).toFixed(2))));
  };

  const handleResetZoom = () => {
    setZoomLevel(1.0);
  };

  return (
    <div
      ref={containerRef}
      className={`relative w-full bg-slate-950 rounded-2xl sm:rounded-3xl overflow-hidden border border-slate-800 shadow-2xl flex items-center justify-center select-none transition-all ${
        isFullscreen
          ? 'fixed inset-0 z-50 rounded-none w-screen h-screen border-none'
          : 'aspect-[4/3] sm:aspect-[16/10] max-h-[65vh] sm:max-h-none'
      }`}
    >



      {/* Active Violation Alert Banner (Top Center) */}
      {reviewTracks.length > 0 && (
        <div className="absolute top-3.5 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-rose-600/90 border border-rose-400 text-white text-xs font-bold shadow-lg shadow-rose-950/80 backdrop-blur-md animate-bounce">
          <AlertTriangle size={15} className="animate-spin" />
          <span>PHÁT HIỆN {reviewTracks.length} THÍ SINH NGHI VẤN VI PHẠM</span>
        </div>
      )}

      {/* Zoomable Video & Canvas Container */}
      <div 
        className="w-full h-full relative flex items-center justify-center overflow-hidden"
        style={{
          transform: `scale(${zoomLevel})`,
          transformOrigin: 'center center',
          transition: 'transform 0.2s ease-out'
        }}
      >
        {/* Realtime Video Stream */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`w-full h-full object-contain ${
            isFrontCamera ? 'scale-x-[-1]' : ''
          }`}
          style={{ display: isStreaming ? 'block' : 'none' }}
        />

        {/* 60 FPS Smooth Interpolated Canvas Bounding Box & Status Overlay */}
        {isStreaming && showOverlay && (
          <TrackOverlay
            tracks={tracks}
            videoDimensions={videoDimensions}
            facingMode={facingMode}
          />
        )}
      </div>

      {/* Camera Live Status Badge (Top-Left HUD) */}
      {isStreaming && (
        <div className="absolute top-3 left-4 flex flex-wrap items-center gap-1.5 sm:gap-2 z-20 pointer-events-none">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-700/80 text-[11px] font-semibold text-slate-200 backdrop-blur-md shadow-lg">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse shadow-sm shadow-rose-500" />
            <span className="truncate max-w-[160px] sm:max-w-[260px]">
              {activeCameraLabel}
            </span>
          </div>

          {videoDimensions.width > 0 && (
            <span className="hidden sm:inline-block px-2 py-1 rounded-lg bg-slate-900/90 border border-slate-800 text-[10px] font-mono text-cyan-400 backdrop-blur-md">
              {videoDimensions.width}×{videoDimensions.height}
            </span>
          )}

          {zoomLevel > 1.0 && (
            <span className="px-2 py-1 rounded-lg bg-blue-950/90 border border-blue-700/80 text-[10px] font-mono font-bold text-blue-300 backdrop-blur-md shadow-sm">
              {zoomLevel.toFixed(2)}×
            </span>
          )}
        </div>
      )}

      {/* Interactive Quick Toolbar (Top-Right HUD: Zoom, Fullscreen, AI Box Toggle) */}
      {isStreaming && (
        <div className="absolute top-3 right-4 flex items-center gap-1.5 z-20">
          {/* Zoom Controls */}
          <div className="flex items-center bg-slate-900/90 border border-slate-700/80 rounded-xl p-0.5 backdrop-blur-md shadow-lg text-slate-200">
            <button
              type="button"
              onClick={handleZoomOut}
              disabled={zoomLevel <= 1.0}
              className="p-1.5 hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent rounded-lg text-slate-300 hover:text-white transition-colors"
              title="Thu nhỏ camera"
            >
              <ZoomOut size={15} />
            </button>

            {zoomLevel > 1.0 ? (
              <button
                type="button"
                onClick={handleResetZoom}
                className="px-1.5 text-[10px] font-mono font-bold text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5 transition-colors"
                title="Đặt lại mức zoom 1.0x"
              >
                <span>{zoomLevel.toFixed(1)}x</span>
                <RotateCcw size={10} />
              </button>
            ) : (
              <span className="px-1 text-[10px] font-mono text-slate-400">1.0x</span>
            )}

            <button
              type="button"
              onClick={handleZoomIn}
              disabled={zoomLevel >= 3.0}
              className="p-1.5 hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent rounded-lg text-slate-300 hover:text-white transition-colors"
              title="Phóng to camera"
            >
              <ZoomIn size={15} />
            </button>
          </div>

          {/* Toggle AI Bounding Box Overlay */}
          <button
            type="button"
            onClick={() => setShowOverlay(prev => !prev)}
            className={`p-2 rounded-xl border backdrop-blur-md shadow-lg text-xs font-semibold transition-all ${
              showOverlay
                ? 'bg-slate-900/90 border-slate-700/80 text-cyan-400 hover:bg-slate-800'
                : 'bg-rose-950/80 border-rose-700/80 text-rose-300 hover:bg-rose-900/80'
            }`}
            title={showOverlay ? 'Ẩn khung Bounding Box AI' : 'Hiện khung Bounding Box AI'}
          >
            {showOverlay ? <Eye size={15} /> : <EyeOff size={15} />}
          </button>

          {/* Fullscreen Expand / Collapse */}
          <button
            type="button"
            onClick={handleToggleFullscreen}
            className="p-2 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 text-slate-200 backdrop-blur-md shadow-lg transition-colors"
            title={isFullscreen ? 'Thu nhỏ cửa sổ' : 'Phóng to toàn màn hình'}
          >
            {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </div>
      )}

      {/* Idle / Unstarted Camera Placeholder */}
      {!isStreaming && !error && (
        <div className="flex flex-col items-center justify-center gap-3.5 p-6 text-center text-slate-400 max-w-sm z-10">
          <div className="w-16 h-16 rounded-3xl bg-slate-900/90 border border-slate-700/80 flex items-center justify-center text-cyan-400 shadow-2xl relative">
            <Camera size={30} />
            <span className="w-3 h-3 rounded-full bg-cyan-400 animate-ping absolute -top-1 -right-1" />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-bold text-slate-100 flex items-center justify-center gap-1.5">
              <span>Hệ Thống Sẵn Sàng Giám Sát</span>
            </h3>
            <p className="text-[11px] sm:text-xs text-slate-400 mt-1.5 leading-relaxed">
              Bấm <strong className="text-blue-400">"Bật Camera"</strong> hoặc <strong className="text-indigo-400">"Tải Video Test"</strong> bên dưới. AI sẽ tự động lấy mẫu tư thế và theo dõi thời gian thực.
            </p>
          </div>
        </div>
      )}

      {/* Camera Error Message Banner */}
      {error && (
        <div className="absolute inset-4 m-auto h-fit bg-rose-950/95 border border-rose-700 text-rose-200 text-xs rounded-2xl p-4 flex flex-col gap-3 backdrop-blur-md z-30 shadow-2xl max-w-md">
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
