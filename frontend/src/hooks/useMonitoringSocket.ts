import { useState, useRef, useCallback, useEffect } from 'react';
import { 
  TrackResult, 
  MonitoringEvent, 
  SocketConnectionState, 
  EventReviewStatus,
  MonitoringResult
} from '../types/monitoring';
import { 
  USE_MOCK_DATA, 
  API_BASE_URL, 
  INITIAL_MOCK_TRACKS, 
  INITIAL_MOCK_EVENTS 
} from '../constants/config';

export function useMonitoringSocket(isSessionActive: boolean) {
  const [connectionState, setConnectionState] = useState<SocketConnectionState>('disconnected');
  const [tracks, setTracks] = useState<TrackResult[]>([]);
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const [fps, setFps] = useState<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [sessionId, setSessionId] = useState<string>('session-local-01');

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const inFlightFrameRef = useRef<boolean>(false);
  const fpsTimestampsRef = useRef<number[]>([]);
  const mockIntervalRef = useRef<number | null>(null);

  // Update FPS calculation
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
  // 1. MOCK DATA ENGINE (When USE_MOCK_DATA === true)
  // -------------------------------------------------------------
  useEffect(() => {
    if (!USE_MOCK_DATA) return;

    if (!isSessionActive) {
      setConnectionState('disconnected');
      setTracks([]);
      setFps(0);
      setLatencyMs(0);
      if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current);
        mockIntervalRef.current = null;
      }
      return;
    }

    setConnectionState('connected');
    setTracks(INITIAL_MOCK_TRACKS);
    setEvents(INITIAL_MOCK_EVENTS);

    let mockTick = 0;
    mockIntervalRef.current = window.setInterval(() => {
      mockTick += 1;
      recordFrameTelemetry(32 + Math.floor(Math.sin(mockTick) * 8));

      // Slightly animate mock candidates
      setTracks(prev => {
        if (prev.length === 0) return INITIAL_MOCK_TRACKS;
        return prev.map(t => {
          if (t.track_id === 1) {
            // Calibrating progresses: 12 -> 20
            const nextSamples = Math.min(20, t.calibration_samples + 1);
            return {
              ...t,
              calibration_samples: nextSamples,
              status: nextSamples >= 20 ? 'WITHIN_THRESHOLDS' : 'CALIBRATING'
            };
          }
          if (t.track_id === 3) {
            // Observing slight yaw fluctuation
            return {
              ...t,
              yaw_delta_deg: Number((38.0 + Math.sin(mockTick * 0.5) * 4).toFixed(1)),
              turning_duration_ms: (t.turning_duration_ms || 800) + 200
            };
          }
          if (t.track_id === 4) {
            // Review state persistent
            return {
              ...t,
              yaw_delta_deg: Number((44.0 + Math.cos(mockTick * 0.3) * 3).toFixed(1)),
              turning_duration_ms: (t.turning_duration_ms || 1700) + 200
            };
          }
          return t;
        });
      });
    }, 200); // 5 FPS

    return () => {
      if (mockIntervalRef.current) {
        clearInterval(mockIntervalRef.current);
      }
    };
  }, [isSessionActive, recordFrameTelemetry]);

  // -------------------------------------------------------------
  // 2. REAL WEBSOCKET CLIENT (When USE_MOCK_DATA === false)
  // -------------------------------------------------------------
  const connectWebSocket = useCallback(() => {
    if (USE_MOCK_DATA || !isSessionActive) return;

    if (!API_BASE_URL) {
      setConnectionState('error');
      console.warn('VITE_API_BASE_URL is not set.');
      return;
    }

    setConnectionState('connecting');
    const newSessionId = `session-${Date.now()}`;
    setSessionId(newSessionId);

    const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + `/ws/sessions/${newSessionId}`;
    
    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnectionState('connected');
        // Initial auth ticket
        ws.send(JSON.stringify({ type: 'auth', ws_ticket: 'demo-ticket-2026' }));
      };

      ws.onmessage = (event) => {
        try {
          const data: MonitoringResult = JSON.parse(event.data);
          if (data.type === 'result') {
            inFlightFrameRef.current = false;
            setTracks(data.tracks || []);
            recordFrameTelemetry(data.processing_ms || 0);

            // If backend returned new events
            if (data.new_event_ids && data.new_event_ids.length > 0) {
              // Add events
              data.tracks.filter(t => t.status === 'REVIEW').forEach(track => {
                setEvents(prevEvents => {
                  if (prevEvents.some(e => e.track_id === track.track_id && e.review_status === 'PENDING')) {
                    return prevEvents;
                  }
                  const newEvt: MonitoringEvent = {
                    event_id: `evt-${Date.now()}`,
                    session_id: newSessionId,
                    track_id: track.track_id,
                    reasons: track.reasons.length > 0 ? track.reasons : ['Nghi vấn tư thế'],
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
          }
        } catch (err) {
          console.error('WS JSON parse error:', err);
        }
      };

      ws.onerror = () => {
        setConnectionState('error');
      };

      ws.onclose = () => {
        setConnectionState('disconnected');
        inFlightFrameRef.current = false;
        // Auto reconnect if session is still active
        if (isSessionActive) {
          setConnectionState('reconnecting');
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connectWebSocket();
          }, 3000);
        }
      };

      wsRef.current = ws;
    } catch (err) {
      setConnectionState('error');
      console.error('WebSocket initialization error:', err);
    }
  }, [isSessionActive, recordFrameTelemetry]);

  useEffect(() => {
    if (!USE_MOCK_DATA) {
      if (isSessionActive) {
        connectWebSocket();
      } else {
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        setConnectionState('disconnected');
        setTracks([]);
      }
    }
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [isSessionActive, connectWebSocket]);

  // Send Frame to WebSocket (Guarded with 1 in-flight frame limit)
  const sendFrame = useCallback((base64: string, width: number, height: number) => {
    if (USE_MOCK_DATA || !isSessionActive || !wsRef.current) return;
    if (wsRef.current.readyState !== WebSocket.OPEN) return;
    if (inFlightFrameRef.current) return; // Drop frame to prevent backpressure latency

    inFlightFrameRef.current = true;
    const msg = {
      type: 'frame',
      frame_id: Date.now(),
      captured_at_ms: Date.now(),
      width,
      height,
      jpeg_base64: base64
    };
    wsRef.current.send(JSON.stringify(msg));
  }, [isSessionActive]);

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
    link.download = `exam_events_${sessionId}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [events, sessionId]);

  // Export Summary JSON
  const exportJson = useCallback(() => {
    const payload = {
      session_id: sessionId,
      exported_at: new Date().toISOString(),
      events_count: events.length,
      events,
      tracks
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `exam_summary_${sessionId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [sessionId, events, tracks]);

  return {
    connectionState,
    tracks,
    events,
    fps,
    latencyMs,
    sessionId,
    sendFrame,
    updateEventStatus,
    exportCsv,
    exportJson
  };
}
