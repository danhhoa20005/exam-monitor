/**
 * Domain types for Exam Posture Monitoring Frontend
 */

export type TrackStatus =
  | 'CALIBRATING'
  | 'WITHIN_THRESHOLDS'
  | 'OBSERVING'
  | 'REVIEW'
  | 'POSE_UNAVAILABLE';

export interface TrackResult {
  track_id: number;
  bbox_xyxy_norm: [number, number, number, number]; // [x1, y1, x2, y2] normalized (0.0 to 1.0)
  detection_confidence?: number;
  pose_valid: boolean;
  calibration_samples: number; // 0 to 20
  status: TrackStatus;
  reasons: string[];
  yaw_delta_deg?: number;
  nose_drop_ratio?: number;
  turning_duration_ms?: number;
  bending_duration_ms?: number;
  activity?: "attentive" | "hand_raised" | "inattentive" | string;
}

export interface MonitoringResult {
  type: 'result';
  session_id: string;
  frame_id: number;
  captured_at_ms: number;
  processing_ms?: number;
  frame_size: [number, number];
  tracks: TrackResult[];
  new_event_ids?: string[];
}

export type EventReviewStatus = 'PENDING' | 'NEEDS_REVIEW' | 'CONFIRMED' | 'DISMISSED';

export interface MonitoringEvent {
  event_id: string;
  session_id: string;
  track_id: number;
  reasons: string[];
  start_ms: number;
  duration_ms: number;
  max_yaw_delta?: number;
  max_nose_drop?: number;
  review_status: EventReviewStatus;
  reviewer?: string;
  reviewed_at?: string;
}

export type SocketConnectionState = 
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error';

export type CameraFacingMode = 'user' | 'environment';

export interface ModelConnectionConfig {
  apiUrl?: string;
  wsUrl: string;
  sessionId: string;
  targetFps: number;
  jpegQuality: number;
  targetWidth: number;
  targetHeight: number;
  authTicket: string;
}

