import { useState, useRef, useCallback, useEffect } from 'react';
import { 
  TrackResult, 
  MonitoringEvent, 
  SocketConnectionState, 
  EventReviewStatus,
  ModelConnectionConfig,
  CameraFacingMode
} from '../types/monitoring';
import { API_BASE_URL, WS_BASE_URL } from '../constants/config';
import { 
  ClientAuthMessage, 
  ClientFrameMessage, 
  ServerMessage 
} from '../types/protocol';

export const DEFAULT_MODEL_CONFIG: ModelConnectionConfig = {
  wsUrl: (WS_BASE_URL || API_BASE_URL.replace(/^http/, 'ws'))
    ? `${WS_BASE_URL || API_BASE_URL.replace(/^http/, 'ws')}/ws/sessions/session-01`
    : (import.meta.env.PROD ? '' : 'ws://127.0.0.1:8000/ws/sessions/session-01'),
  sessionId: 'session-local-01',
  targetFps: 5,
  jpegQuality: 0.75,
  targetWidth: 640,
  targetHeight: 480,
  authTicket: 'demo-ticket-2026'
};

export function useMonitoringSocket(isCameraStreaming: boolean) {
  const [connectionState, setConnectionState] = useState<SocketConnectionState>('disconnected');
  const [tracks, setTracks] = useState<TrackResult[]>([]);
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const [fps, setFps] = useState<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [modelConfig, setModelConfig] = useState<ModelConnectionConfig>(DEFAULT_MODEL_CONFIG);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const inFlightFrameRef = useRef<boolean>(false);
  const fpsTimestampsRef = useRef<number[]>([]);
  const isComponentMountedRef = useRef<boolean>(true);

  // Update AI Model Connection Configuration
  const updateModelConfig = useCallback((newConfig: Partial<ModelConnectionConfig>) => {
    setModelConfig(prev => ({ ...prev, ...newConfig }));
  }, []);

  // Record FPS and Latency
  const recordFrameTelemetry = useCallback((processingMs: number = 0) => {
    const now = performance.now();
    fpsTimestampsRef.current.push(now);
    if (fpsTimestampsRef.current.length > 15) {
      fpsTimestampsRef.current.shift();
    }
    if (fpsTimestampsRef.current.length > 1) {
      const elapsed = (now - fpsTimestampsRef.current[0]) / 1000;
      const currentFps = Math.round((fpsTimestampsRef.current.length - 1) / elapsed);
      setFps(Math.min(60, Math.max(1, currentFps)));
    }
    setLatencyMs(processingMs);
  }, []);

  // -------------------------------------------------------------
  // REAL WEBSOCKET CLIENT (100% Live AI Model Backend)
  // -------------------------------------------------------------
  const connectWebSocket = useCallback(() => {
    if (!isComponentMountedRef.current) return;

    // Clean up existing socket before creating new one
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (e) {
        // ignore
      }
      wsRef.current = null;
    }

    const wsUrl = modelConfig.wsUrl;
    if (!wsUrl) {
      setConnectionState('error');
      console.error('AI backend is not configured. Set VITE_API_BASE_URL or VITE_WS_URL in Vercel.');
      // Stop infinite reconnect loop in Vercel if wsUrl is missing
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      return;
    }
    setConnectionState('connecting');

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (!isComponentMountedRef.current) return;
        // The socket is open, but the AI session is authenticated only after
        // the backend returns session_info.
        setConnectionState('connecting');
        // Send initial auth ticket
        const authMsg: ClientAuthMessage = {
          type: 'auth',
          ws_ticket: modelConfig.authTicket,
          session_id: modelConfig.sessionId,
          client_timestamp: Date.now()
        };
        ws.send(JSON.stringify(authMsg));
      };

      ws.onmessage = (event) => {
        if (!isComponentMountedRef.current) return;
        try {
          const data: ServerMessage = JSON.parse(event.data);
          
          if (data.type === 'result') {
            inFlightFrameRef.current = false;
            setTracks(data.tracks || []);
            recordFrameTelemetry(data.processing_ms || 0);

            // Append newly triggered suspicious events from real AI model
            if (data.new_event_ids && data.new_event_ids.length > 0) {
              data.tracks.filter(t => t.status === 'REVIEW').forEach(track => {
                setEvents(prevEvents => {
                  if (prevEvents.some(e => e.track_id === track.track_id && e.review_status === 'PENDING')) {
                    return prevEvents;
                  }
                  const newEvt: MonitoringEvent = {
                    event_id: `evt-${Date.now()}-${track.track_id}`,
                    session_id: modelConfig.sessionId,
                    track_id: track.track_id,
                    reasons: track.reasons.length > 0 ? track.reasons : ['Nghi vấn tư thế bất thường'],
                    start_ms: data.captured_at_ms,
                    duration_ms: Math.max(track.turning_duration_ms || 0, track.bending_duration_ms || 0, 1500),
                    max_yaw_delta: track.yaw_delta_deg,
                    max_nose_drop: track.nose_drop_ratio,
                    review_status: 'PENDING'
                  };
                  return [newEvt, ...prevEvents];
                });
              });
            }
          } else if (data.type === 'session_info') {
            setConnectionState('connected');
          } else if (data.type === 'pong') {
            const rtt = Date.now() - data.client_timestamp;
            setLatencyMs(rtt);
          } else if (data.type === 'error') {
            inFlightFrameRef.current = false;
            setConnectionState('error');
            console.error('AI Model WebSocket error message:', data.message);
          }
        } catch (err) {
          console.error('WS JSON parse error:', err);
        }
      };

      ws.onerror = () => {
        if (!isComponentMountedRef.current) return;
        setConnectionState('error');
      };

      ws.onclose = () => {
        if (!isComponentMountedRef.current) return;
        setConnectionState('disconnected');
        inFlightFrameRef.current = false;
        
        // Auto-reconnect with 3s backoff
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = window.setTimeout(() => {
          if (isComponentMountedRef.current) {
            setConnectionState('reconnecting');
            connectWebSocket();
          }
        }, 3000);
      };

      wsRef.current = ws;
    } catch (err) {
      if (!isComponentMountedRef.current) return;
      setConnectionState('error');
      console.error('WebSocket connection failed:', err);
    }
  }, [modelConfig, recordFrameTelemetry]);

  // Connect on mount and re-connect when config changes
  useEffect(() => {
    isComponentMountedRef.current = true;
    connectWebSocket();

    return () => {
      isComponentMountedRef.current = false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connectWebSocket]);

  // Send Frame to WebSocket (Guarded with 1 in-flight frame limit)
  const sendFrame = useCallback((
    base64: string, 
    width: number, 
    height: number,
    facingMode: CameraFacingMode = 'environment'
  ) => {
    if (!isCameraStreaming || !wsRef.current) return;
    if (wsRef.current.readyState !== WebSocket.OPEN) return;
    if (inFlightFrameRef.current) return; // Drop frame to avoid backpressure

    inFlightFrameRef.current = true;
    const msg: ClientFrameMessage = {
      type: 'frame',
      frame_id: Date.now(),
      session_id: modelConfig.sessionId,
      captured_at_ms: Date.now(),
      width,
      height,
      facing_mode: facingMode,
      jpeg_base64: base64
    };
    wsRef.current.send(JSON.stringify(msg));
  }, [isCameraStreaming, modelConfig.sessionId]);

  // Supervisor Action: Update Event Status
  const updateEventStatus = useCallback((eventId: string, status: EventReviewStatus, reviewer: string = 'Giám thị') => {
    setEvents(prev => prev.map(e => {
      if (e.event_id === eventId) {
        return {
          ...e,
          review_status: status,
          reviewer,
          reviewed_at: new Date().toISOString()
        };
      }
      return e;
    }));
  }, []);

  // Export Events CSV
  const exportCsv = useCallback(() => {
    const headers = ['Event ID', 'Track ID', 'Lý do', 'Bắt đầu', 'Thời lượng (ms)', 'Trạng thái', 'Người duyệt'];
    const rows = events.map(e => [
      e.event_id,
      e.track_id,
      e.reasons.join('; '),
      new Date(e.start_ms).toLocaleTimeString(),
      e.duration_ms,
      e.review_status,
      e.reviewer || ''
    ]);

    const csvContent = '\uFEFF' + [
      headers.join(','),
      ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `exam_events_${modelConfig.sessionId}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [events, modelConfig.sessionId]);

  // Export Summary JSON
  const exportJson = useCallback(() => {
    const payload = {
      session_id: modelConfig.sessionId,
      exported_at: new Date().toISOString(),
      events_count: events.length,
      events,
      tracks
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `exam_summary_${modelConfig.sessionId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [modelConfig.sessionId, events, tracks]);

  return {
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
  };
}
