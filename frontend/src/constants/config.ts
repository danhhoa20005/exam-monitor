import { TrackStatus } from '../types/monitoring';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
export const WS_BASE_URL = (import.meta.env.VITE_WS_URL || '').replace(/\/+$/, '');

export function getStoredApiUrl(): string {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('visionguard_api_base_url');
    if (saved && saved.trim()) return saved.trim().replace(/\/+$/, '');
  }
  return '';
}

export function setStoredApiUrl(url: string): void {
  if (typeof window !== 'undefined') {
    if (!url || !url.trim()) {
      localStorage.removeItem('visionguard_api_base_url');
    } else {
      localStorage.setItem('visionguard_api_base_url', url.trim().replace(/\/+$/, ''));
    }
  }
}

export const CLOUDFLARE_TUNNEL_URL = 'https://wendy-recordings-clean-industries.trycloudflare.com';
export const LOCAL_BACKEND_URL = 'http://localhost:8000';

export function getEffectiveApiBaseUrl(): string {
  const saved = getStoredApiUrl();
  if (saved) return saved;
  if (API_BASE_URL) return API_BASE_URL;
  if (import.meta.env.DEV) return 'http://127.0.0.1:8000';
  if (typeof window !== 'undefined' && window.location) {
    if (window.location.hostname.includes('vercel.app')) {
      return CLOUDFLARE_TUNNEL_URL;
    }
    if (window.location.origin && window.location.port !== '5173') {
      return window.location.origin.replace(/\/+$/, '');
    }
  }
  return 'http://127.0.0.1:8000';
}

// Local development uses the backend started by the project script. In a
// production build served by FastAPI, keep the API on the current origin.
export const EFFECTIVE_API_BASE_URL = getEffectiveApiBaseUrl();


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
