import React, { useState, useEffect, useCallback } from 'react';
import { CameraView } from '../components/camera/CameraView';
import { CameraControls } from '../components/camera/CameraControls';
import { TrackCard } from '../components/monitoring/TrackCard';
import { EventPanel } from '../components/monitoring/EventPanel';
import { Header } from '../components/common/Header';
import { ModelConfigModal } from '../components/common/ModelConfigModal';
import { useCamera } from '../hooks/useCamera';
import { useMonitoringSocket } from '../hooks/useMonitoringSocket';
import { Users, Info, Radio } from 'lucide-react';

export const MonitorPage: React.FC = () => {
  const [isConfigOpen, setIsConfigOpen] = useState<boolean>(false);

  // Camera Management Hook
  const {
    videoRef,
    isStreaming,
    facingMode,
    activeDeviceId,
    activeCameraLabel,
    availableDevices,
    error: cameraError,
    videoDimensions,
    startCamera,
    stopCamera,
    toggleCamera,
    selectDevice,
    captureFrame
  } = useCamera();

  // Monitoring WebSocket & AI Model State Management Hook (100% Live AI)
  const {
    connectionState,
    tracks,
    events,
    fps,
    latencyMs,
    modelConfig,
    updateModelConfig,
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

  // Frame Capture Interval (Streams camera frames directly to YOLOv8 & MediaPipe Backend)
  useEffect(() => {
    if (!isStreaming) return;

    const intervalMs = Math.max(50, Math.floor(1000 / (modelConfig.targetFps || 5)));
    const interval = setInterval(() => {
      const frame = captureFrame(
        modelConfig.targetWidth || 640, 
        modelConfig.targetHeight || 480, 
        modelConfig.jpegQuality || 0.75
      );
      if (frame) {
        sendFrame(frame.base64, frame.width, frame.height, frame.facingMode);
      }
    }, intervalMs);

    return () => clearInterval(interval);
  }, [isStreaming, modelConfig, captureFrame, sendFrame]);

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
        onOpenConfig={() => setIsConfigOpen(true)}
      />

      {/* Main Responsive Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-4 md:p-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6">
          
          {/* Left / Top Section: Camera & Touch Controls (Desktop ~65% / col-span-7 or 8) */}
          <section className="lg:col-span-7 xl:col-span-8 flex flex-col gap-3.5">
            <CameraView
              videoRef={videoRef}
              isStreaming={isStreaming}
              facingMode={facingMode}
              activeCameraLabel={activeCameraLabel}
              tracks={tracks}
              videoDimensions={videoDimensions}
              error={cameraError}
              onRetry={handleStart}
            />

            {/* Mobile & Tablet Control Buttons */}
            <CameraControls
              isStreaming={isStreaming}
              facingMode={facingMode}
              activeDeviceId={activeDeviceId}
              availableDevices={availableDevices}
              targetFps={modelConfig.targetFps || 10}
              onUpdateFps={(fps) => updateModelConfig({ targetFps: fps })}
              onStart={handleStart}
              onStop={handleStop}
              onToggleCamera={toggleCamera}
              onSelectDevice={selectDevice}
            />

            {/* Instructions & Calibration Helper Box */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 text-xs text-slate-400 shadow-sm">
              <div className="flex items-center gap-2 font-bold text-slate-200 mb-2">
                <Info size={15} className="text-blue-400" />
                <span>Quy Trình Giám Sát AI Realtime (Model `best.pt`):</span>
              </div>
              <ul className="list-disc list-inside space-y-1.5 text-[11px] text-slate-400 leading-relaxed">
                <li>
                  Mặc định hệ thống sử dụng <strong className="text-slate-200">Camera Sau</strong> để bao quát rộng, hoặc bấm <strong className="text-blue-300">"Chuyển: Cam Trước"</strong> khi giám sát góc cá nhân.
                </li>
                <li>
                  Sử dụng các nút ở góc trên camera để <strong className="text-blue-300">Phóng to (Zoom 1x-3x)</strong>, <strong className="text-blue-300">Toàn màn hình</strong> hoặc <strong className="text-blue-300">Bật/tắt khung AI</strong>.
                </li>
                <li>
                  Thí sinh ngồi thẳng hướng mặt về camera để AI lấy <strong className="text-slate-200">20 mẫu mốc tham chiếu</strong> ban đầu.
                </li>
                <li>
                  Khi có hành vi quay đầu (<strong className="text-amber-300">&gt;35°</strong>) hoặc cúi người (<strong className="text-amber-300">&gt;15%</strong>) kéo dài <strong className="text-rose-300">≥ 1.5 giây</strong>, hệ thống phát nhãn <strong className="text-rose-400">"Nghi vấn — cần xem lại"</strong> để giám thị xử lý.
                </li>
              </ul>
            </div>
          </section>

          {/* Right / Bottom Section: Active Tracked Candidates & Suspicious Events (Desktop ~35% / col-span-5 or 4) */}
          <section className="lg:col-span-5 xl:col-span-4 flex flex-col gap-5">
            
            {/* Active Candidates List */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users size={18} className="text-blue-400" />
                  <h2 className="text-sm font-bold text-slate-100">
                    Đối Tượng Đang Theo Dõi ({tracks.length})
                  </h2>
                </div>
                <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-800/60">
                  <Radio size={11} className="animate-pulse" />
                  <span>Live YOLOv8m</span>
                </div>
              </div>

              <div className="space-y-2.5 max-h-[260px] sm:max-h-[300px] overflow-y-auto pr-1">
                {tracks.length === 0 ? (
                  <div className="p-6 text-center text-slate-500 text-xs bg-slate-900/40 rounded-2xl border border-slate-800/60 leading-relaxed">
                    {isStreaming 
                      ? "Đang quét hình ảnh qua Model AI — Chưa phát hiện đối tượng trong khung hình."
                      : "Camera chưa mở. Nhấn 'Mở Camera' để bắt đầu giám sát."}
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

      {/* Model Integration & Connection Settings Modal */}
      <ModelConfigModal
        isOpen={isConfigOpen}
        onClose={() => setIsConfigOpen(false)}
        connectionState={connectionState}
        modelConfig={modelConfig}
        onUpdateConfig={updateModelConfig}
      />
    </div>
  );
};
