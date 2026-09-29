import React, { useState } from 'react';
import { X, Settings, Radio, Cpu, Sparkles, Server, CheckCircle2, ShieldCheck, Code2 } from 'lucide-react';
import { ModelConnectionConfig, SocketConnectionState } from '../../types/monitoring';

interface ModelConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  isMockEnabled: boolean;
  onSetMockMode: (enabled: boolean) => void;
  connectionState: SocketConnectionState;
  modelConfig: ModelConnectionConfig;
  onUpdateConfig: (newConfig: Partial<ModelConnectionConfig>) => void;
}

export const ModelConfigModal: React.FC<ModelConfigModalProps> = ({
  isOpen,
  onClose,
  isMockEnabled,
  onSetMockMode,
  connectionState,
  modelConfig,
  onUpdateConfig
}) => {
  const [formState, setFormState] = useState<ModelConnectionConfig>({ ...modelConfig });
  const [activeTab, setActiveTab] = useState<'config' | 'protocol'>('config');

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdateConfig(formState);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-md animate-fadeIn">
      <div 
        className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/80 bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Settings size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">
                Cài Đặt Kết Nối AI & Camera
              </h2>
              <p className="text-xs text-slate-400">
                Cấu hình cổng chờ ghép nối AI Model (YOLOv8 + ByteTrack + MediaPipe)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 bg-slate-950/40 px-5 pt-2 gap-4 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab('config')}
            className={`pb-2.5 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'config'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            <Server size={14} />
            <span>Cấu Hình Kết Nối</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('protocol')}
            className={`pb-2.5 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'protocol'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-300'
            }`}
          >
            <Code2 size={14} />
            <span>Chuẩn Protocol Ghép Model</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-5 flex-1">
          {activeTab === 'config' ? (
            <form id="model-config-form" onSubmit={handleSave} className="space-y-4">
              {/* Mode Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">
                  Chế Độ Vận Hành:
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => onSetMockMode(true)}
                    className={`p-3 rounded-xl border text-left flex flex-col gap-1 transition-all ${
                      isMockEnabled
                        ? 'bg-blue-950/50 border-blue-500 text-blue-100 shadow-md shadow-blue-500/10'
                        : 'bg-slate-800/50 border-slate-700/70 text-slate-400 hover:bg-slate-800'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 text-xs font-bold">
                      <Cpu size={15} className={isMockEnabled ? 'text-blue-400' : 'text-slate-400'} />
                      <span>Giả Lập (Mock Demo)</span>
                    </div>
                    <span className="text-[11px] text-slate-400 leading-tight">
                      Mô phỏng 5 trạng thái tư thế chuẩn không cần backend.
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => onSetMockMode(false)}
                    className={`p-3 rounded-xl border text-left flex flex-col gap-1 transition-all ${
                      !isMockEnabled
                        ? 'bg-emerald-950/50 border-emerald-500 text-emerald-100 shadow-md shadow-emerald-500/10'
                        : 'bg-slate-800/50 border-slate-700/70 text-slate-400 hover:bg-slate-800'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 text-xs font-bold">
                      <Radio size={15} className={!isMockEnabled ? 'text-emerald-400' : 'text-slate-400'} />
                      <span>Live AI Model (WebSocket)</span>
                    </div>
                    <span className="text-[11px] text-slate-400 leading-tight">
                      Gửi frame camera trực tiếp tới server AI qua WebSocket.
                    </span>
                  </button>
                </div>
              </div>

              {/* WebSocket URL */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  WebSocket Endpoint (URL Backend AI):
                </label>
                <input
                  type="text"
                  value={formState.wsUrl}
                  onChange={(e) => setFormState(prev => ({ ...prev, wsUrl: e.target.value }))}
                  placeholder="ws://127.0.0.1:8000/ws/sessions/session-01"
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-xs text-slate-200 font-mono focus:border-blue-500 focus:outline-none"
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  Ví dụ local: <code className="text-blue-300">ws://127.0.0.1:8000/ws/sessions/session-01</code>
                </p>
              </div>

              {/* Session ID & Ticket */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Mã Phòng / Session ID:
                  </label>
                  <input
                    type="text"
                    value={formState.sessionId}
                    onChange={(e) => setFormState(prev => ({ ...prev, sessionId: e.target.value }))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Auth Token / Ticket:
                  </label>
                  <input
                    type="text"
                    value={formState.authTicket}
                    onChange={(e) => setFormState(prev => ({ ...prev, authTicket: e.target.value }))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Streaming Framerate & Resolution */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Tốc độ gửi Frame (FPS):
                  </label>
                  <select
                    value={formState.targetFps}
                    onChange={(e) => setFormState(prev => ({ ...prev, targetFps: Number(e.target.value) }))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
                  >
                    <option value={3}>3 FPS (Tiết kiệm băng thông di động)</option>
                    <option value={5}>5 FPS (Khuyến nghị chuẩn phòng thi)</option>
                    <option value={10}>10 FPS (Độ mượt cao)</option>
                    <option value={15}>15 FPS (Realtime chuyên sâu)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Độ phân giải gửi Frame:
                  </label>
                  <select
                    value={`${formState.targetWidth}x${formState.targetHeight}`}
                    onChange={(e) => {
                      const [w, h] = e.target.value.split('x').map(Number);
                      setFormState(prev => ({ ...prev, targetWidth: w, targetHeight: h }));
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
                  >
                    <option value="640x480">640 × 480 (Tối ưu cho YOLOv8 di động)</option>
                    <option value="960x540">960 × 540 (Cân bằng chi tiết)</option>
                    <option value="1280x720">1280 × 720 (HD 720p)</option>
                  </select>
                </div>
              </div>

              {/* Status info box */}
              <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 flex items-center justify-between text-xs">
                <span className="text-slate-400">Trạng thái kết nối hiện tại:</span>
                <span className="font-semibold capitalize text-slate-200 flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${
                    connectionState === 'connected' ? 'bg-emerald-400' : 'bg-amber-400'
                  }`} />
                  {isMockEnabled ? 'Đang chạy Mock Demo' : connectionState}
                </span>
              </div>
            </form>
          ) : (
            <div className="space-y-4 text-xs">
              <div className="bg-blue-950/30 border border-blue-800/60 rounded-xl p-3 text-blue-200 text-xs flex items-start gap-2">
                <Sparkles size={16} className="text-blue-400 shrink-0 mt-0.5" />
                <p>
                  Dưới đây là định dạng JSON chuẩn mà Frontend gửi đi và chờ nhận từ AI model (Python YOLOv8 + ByteTrack + MediaPipe).
                </p>
              </div>

              <div>
                <span className="font-semibold text-slate-200 block mb-1">
                  1. Frame Frontend gửi lên Backend (WebSocket Client -&gt; Server):
                </span>
                <pre className="bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-[11px] text-emerald-300 overflow-x-auto">
{`{
  "type": "frame",
  "frame_id": 1727578900123,
  "session_id": "session-local-01",
  "captured_at_ms": 1727578900123,
  "width": 640,
  "height": 480,
  "facing_mode": "environment", // "user" hoặc "environment"
  "jpeg_base64": "/9j/4AAQSkZJRgABAQ..."
}`}
                </pre>
              </div>

              <div>
                <span className="font-semibold text-slate-200 block mb-1">
                  2. Backend AI trả kết quả về (Server -&gt; Frontend Client):
                </span>
                <pre className="bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-[11px] text-blue-300 overflow-x-auto">
{`{
  "type": "result",
  "session_id": "session-local-01",
  "frame_id": 1727578900123,
  "captured_at_ms": 1727578900123,
  "processing_ms": 32,
  "frame_size": [640, 480],
  "tracks": [
    {
      "track_id": 1,
      "bbox_xyxy_norm": [0.20, 0.15, 0.45, 0.70],
      "pose_valid": true,
      "calibration_samples": 20,
      "status": "WITHIN_THRESHOLDS", // "CALIBRATING" | "WITHIN_THRESHOLDS" | "OBSERVING" | "REVIEW" | "POSE_UNAVAILABLE"
      "reasons": [],
      "yaw_delta_deg": 4.2,
      "nose_drop_ratio": 0.03
    }
  ],
  "new_event_ids": []
}`}
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3.5 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <span className="text-[11px] text-slate-400 flex items-center gap-1">
            <ShieldCheck size={14} className="text-blue-400" />
            <span>Sẵn sàng cho việc ghép model</span>
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Đóng
            </button>
            {activeTab === 'config' && (
              <button
                type="submit"
                form="model-config-form"
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md shadow-blue-600/30 transition-all flex items-center gap-1.5"
              >
                <CheckCircle2 size={14} />
                <span>Lưu Cấu Hình</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
