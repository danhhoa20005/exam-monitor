/**
 * Protocol Specification: Frontend <-> Backend AI Model (WebSocket)
 * Hệ thống Giám Sát Tư Thế Phòng Thi Realtime
 */

import { TrackResult, TrackStatus, EventReviewStatus } from './monitoring';

// 1. Client -> Server: Message Types
export type ClientMessageType = 'auth' | 'frame' | 'config' | 'ping';

export interface ClientAuthMessage {
  type: 'auth';
  ws_ticket?: string;
  session_id: string;
  client_timestamp: number;
}

export interface ClientFrameMessage {
  type: 'frame';
  frame_id: number;
  session_id: string;
  captured_at_ms: number;
  width: number;
  height: number;
  facing_mode: 'user' | 'environment';
  jpeg_base64: string; // JPEG encoded image base64
}

export interface ClientConfigMessage {
  type: 'config';
  session_id: string;
  target_fps?: number;
  confidence_threshold?: number;
}

export interface ClientPingMessage {
  type: 'ping';
  timestamp: number;
}

export type ClientMessage = 
  | ClientAuthMessage 
  | ClientFrameMessage 
  | ClientConfigMessage 
  | ClientPingMessage;

// 2. Server -> Client: Message Types
export type ServerMessageType = 'result' | 'pong' | 'error' | 'session_info';

export interface ServerMonitoringResult {
  type: 'result';
  session_id: string;
  frame_id: number;
  captured_at_ms: number;
  processed_at_ms?: number;
  processing_ms?: number;
  frame_size: [number, number]; // [width, height]
  tracks: TrackResult[];
  new_event_ids?: string[];
}

export interface ServerPongMessage {
  type: 'pong';
  client_timestamp: number;
  server_timestamp: number;
}

export interface ServerErrorMessage {
  type: 'error';
  code: string;
  message: string;
}

export interface ServerSessionInfoMessage {
  type: 'session_info';
  session_id: string;
  status: 'ACTIVE' | 'PAUSED' | 'CLOSED';
  model_info?: {
    detector: string;     // e.g. 'YOLOv8n'
    tracker: string;      // e.g. 'ByteTrack'
    pose_estimator: string; // e.g. 'MediaPipe BlazePose'
  };
}

export type ServerMessage = 
  | ServerMonitoringResult 
  | ServerPongMessage 
  | ServerErrorMessage 
  | ServerSessionInfoMessage;

// Re-export for convenience
export type { TrackResult, TrackStatus, EventReviewStatus };
