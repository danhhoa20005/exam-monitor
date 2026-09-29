import React, { useEffect, useCallback } from 'react';
import { CameraView } from '../components/camera/CameraView';
import { CameraControls } from '../components/camera/CameraControls';
import { TrackCard } from '../components/monitoring/TrackCard';
import { EventPanel } from '../components/monitoring/EventPanel';
import { Header } from '../components/common/Header';
import { useCamera } from '../hooks/useCamera';
import { useMonitoringSocket } from '../hooks/useMonitoringSocket';
import { Users } from 'lucide-react';

export const MonitorPage: React.FC = () => {
  // Camera Management Hook
  const {
    videoRef,
    isStreaming,
    facingMode,
    error: cameraError,
    videoDimensions,
    startCamera,
    stopCamera,
    toggleCamera,
    captureFrame
  } = useCamera();

  // Monitoring WebSocket & State Management Hook
  const {
    connectionState,
    tracks,
    events,
    fps,
    latencyMs,
    sendFrame,
    updateEventStatus,
    exportCsv,
    exportJson
  } = useMonitoringSocket(isStreaming);

  // Handle Start Camera Button
  const handleStart = useCallback(async () => {
    await startCamera();
  }, [startCamera]);

  // Handle Stop Camera Button
  const handleStop = useCallback(() => {
    stopCamera();
  }, [stopCamera]);

  // Frame Capture Interval (Sends JPEG 0.75 @ ~5 FPS when streaming)
  useEffect(() => {
    if (!isStreaming) return;

    const interval = setInterval(() => {
      const frame = captureFrame(640, 480);
      if (frame) {
        sendFrame(frame.base64, frame.width, frame.height);
      }
    }, 200); // 5 FPS (200ms)

    return () => clearInterval(interval);
  }, [isStreaming, captureFrame, sendFrame]);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 antialiased font-sans pb-safe">
      {/* Top Header */}
      <Header
        connectionState={connectionState}
        isStreaming={isStreaming}
        facingMode={facingMode}
        fps={fps}
        latencyMs={latencyMs}
        onStart={handleStart}
        onStop={handleStop}
        onToggleCamera={toggleCamera}
      />

      {/* Main Responsive Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-4 md:p-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6">
          
          {/* Left / Top Section: Camera & Touch Controls (Desktop ~65-70% / col-span-7 or 8) */}
          <section className="lg:col-span-7 xl:col-span-8 flex flex-col gap-3">
            <CameraView
              videoRef={videoRef}
              isStreaming={isStreaming}
              facingMode={facingMode}
              tracks={tracks}
              videoDimensions={videoDimensions}
              error={cameraError}
            />

            {/* Mobile & Tablet Control Buttons */}
            <CameraControls
              isStreaming={isStreaming}
              facingMode={facingMode}
              onStart={handleStart}
              onStop={handleStop}
              onToggleCamera={toggleCamera}
            />

            {/* Instructions helper box */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-3.5 text-xs text-slate-400">
              <span className="font-semibold text-slate-300 block mb-1">
                Hướng Dẫn Giám Sát:
              </span>
              <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-400">
                <li>Bấm <strong>"Bắt đầu"</strong> để mở camera trên điện thoại hoặc máy tính.</li>
                <li>Hệ thống AI sẽ lấy mốc tư thế (0/20 mẫu) trước khi đánh giá.</li>
                <li>Các cảnh báo bất thường được đánh nhãn <strong>"Nghi vấn — cần xem lại"</strong> để giám thị quyết định.</li>
              </ul>
            </div>
          </section>

          {/* Right / Bottom Section: Active Tracked Candidates & Suspicious Events (Desktop ~30-35% / col-span-5 or 4) */}
          <section className="lg:col-span-5 xl:col-span-4 flex flex-col gap-5">
            
            {/* Active Candidates List */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users size={18} className="text-blue-400" />
                  <h2 className="text-sm font-semibold text-slate-100">
                    Đối Tượng Đang Theo Dõi ({tracks.length})
                  </h2>
                </div>
              </div>

              <div className="space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
                {tracks.length === 0 ? (
                  <div className="p-6 text-center text-slate-500 text-xs bg-slate-900/40 rounded-xl border border-slate-800/60">
                    Chưa phát hiện đối tượng nào trong khung hình.
                  </div>
                ) : (
                  tracks.map(track => (
                    <TrackCard key={track.track_id} track={track} />
                  ))
                )}
              </div>
            </div>

            {/* Suspicious Events Panel */}
            <EventPanel
              events={events}
              onUpdateStatus={updateEventStatus}
              onExportCsv={exportCsv}
              onExportJson={exportJson}
            />
          </section>

        </div>
      </main>
    </div>
  );
};
