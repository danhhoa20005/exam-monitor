import { TrackResult, TrackStatus, MonitoringEvent } from '../types/monitoring';

// Default to Live AI Mode (false) so no hardcoded mock yellow/amber boxes overlay the real camera
export const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK === 'true' ? true : false;
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const CALIBRATION_TOTAL_SAMPLES = 20;

export const STATUS_LABELS: Record<TrackStatus, string> = {
  CALIBRATING: 'Đang lấy mốc',
  WITHIN_THRESHOLDS: 'Chưa vượt ngưỡng',
  OBSERVING: 'Đang theo dõi',
  REVIEW: 'Nghi vấn — cần xem lại',
  POSE_UNAVAILABLE: 'Không đủ dữ liệu tư thế'
};

export const STATUS_STYLES: Record<TrackStatus, {
  color: string;
  bgColor: string;
  badgeBg: string;
  badgeText: string;
  borderColor: string;
  glow: string;
}> = {
  CALIBRATING: {
    color: '#3b82f6',
    bgColor: 'rgba(59, 130, 246, 0.12)',
    badgeBg: 'bg-blue-500/15',
    badgeText: 'text-blue-400',
    borderColor: 'border-blue-500/40',
    glow: 'rgba(59, 130, 246, 0.35)'
  },
  WITHIN_THRESHOLDS: {
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.10)',
    badgeBg: 'bg-emerald-500/15',
    badgeText: 'text-emerald-400',
    borderColor: 'border-emerald-500/40',
    glow: 'rgba(16, 185, 129, 0.35)'
  },
  OBSERVING: {
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.15)',
    badgeBg: 'bg-amber-500/15',
    badgeText: 'text-amber-400',
    borderColor: 'border-amber-500/40',
    glow: 'rgba(245, 158, 11, 0.35)'
  },
  REVIEW: {
    color: '#ef4444',
    bgColor: 'rgba(239, 68, 68, 0.20)',
    badgeBg: 'bg-red-500/20',
    badgeText: 'text-red-400',
    borderColor: 'border-red-500/60',
    glow: 'rgba(239, 68, 68, 0.5)'
  },
  POSE_UNAVAILABLE: {
    color: '#64748b',
    bgColor: 'rgba(100, 116, 139, 0.10)',
    badgeBg: 'bg-slate-500/15',
    badgeText: 'text-slate-400',
    borderColor: 'border-slate-500/30',
    glow: 'rgba(100, 116, 139, 0.2)'
  }
};

/**
 * 5 Initial Mock Tracks for Demo Simulation only:
 */
export const INITIAL_MOCK_TRACKS: TrackResult[] = [
  {
    track_id: 1,
    bbox_xyxy_norm: [0.08, 0.15, 0.34, 0.72],
    detection_confidence: 0.94,
    pose_valid: true,
    calibration_samples: 12,
    status: 'CALIBRATING',
    reasons: [],
    yaw_delta_deg: 3.2,
    nose_drop_ratio: 0.02,
    turning_duration_ms: 0,
    bending_duration_ms: 0
  },
  {
    track_id: 2,
    bbox_xyxy_norm: [0.38, 0.18, 0.64, 0.76],
    detection_confidence: 0.92,
    pose_valid: true,
    calibration_samples: 20,
    status: 'WITHIN_THRESHOLDS',
    reasons: [],
    yaw_delta_deg: -4.1,
    nose_drop_ratio: 0.03,
    turning_duration_ms: 0,
    bending_duration_ms: 0
  },
  {
    track_id: 3,
    bbox_xyxy_norm: [0.68, 0.16, 0.94, 0.74],
    detection_confidence: 0.89,
    pose_valid: true,
    calibration_samples: 20,
    status: 'OBSERVING',
    reasons: ['Quay đầu'],
    yaw_delta_deg: 38.5,
    nose_drop_ratio: 0.04,
    turning_duration_ms: 800,
    bending_duration_ms: 0
  },
  {
    track_id: 4,
    bbox_xyxy_norm: [0.22, 0.40, 0.50, 0.95],
    detection_confidence: 0.95,
    pose_valid: true,
    calibration_samples: 20,
    status: 'REVIEW',
    reasons: ['Quay đầu'],
    yaw_delta_deg: 44.2,
    nose_drop_ratio: 0.05,
    turning_duration_ms: 1700,
    bending_duration_ms: 0
  },
  {
    track_id: 5,
    bbox_xyxy_norm: [0.55, 0.42, 0.82, 0.96],
    detection_confidence: 0.78,
    pose_valid: false,
    calibration_samples: 8,
    status: 'POSE_UNAVAILABLE',
    reasons: [],
    yaw_delta_deg: 0,
    nose_drop_ratio: 0,
    turning_duration_ms: 0,
    bending_duration_ms: 0
  }
];

export const INITIAL_MOCK_EVENTS: MonitoringEvent[] = [
  {
    event_id: 'evt-101',
    session_id: 'mock-session-01',
    track_id: 4,
    reasons: ['Quay đầu liên tục (>35°)'],
    start_ms: Date.now() - 1700,
    duration_ms: 1700,
    max_yaw_delta: 44.2,
    max_nose_drop: 0.05,
    review_status: 'PENDING'
  }
];
