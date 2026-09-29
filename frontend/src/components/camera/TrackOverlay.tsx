import React, { useEffect, useRef } from 'react';
import { TrackResult, CameraFacingMode } from '../../types/monitoring';
import { STATUS_STYLES, STATUS_LABELS } from '../../constants/config';

interface TrackOverlayProps {
  tracks: TrackResult[];
  videoDimensions: { width: number; height: number };
  facingMode: CameraFacingMode;
}

export const TrackOverlay: React.FC<TrackOverlayProps> = ({
  tracks,
  videoDimensions,
  facingMode
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Support sharp HiDPI Retina displays on iPhone, iPad, and high-DPI screens
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, rect.height);

    if (tracks.length === 0) return;

    // Compute aspect-ratio math for object-fit: contain compensation
    const containerW = rect.width;
    const containerH = rect.height;
    const vW = videoDimensions.width > 0 ? videoDimensions.width : 640;
    const vH = videoDimensions.height > 0 ? videoDimensions.height : 480;

    const videoAspect = vW / vH;
    const containerAspect = containerW / containerH;

    let renderedW: number;
    let renderedH: number;
    let offsetX: number;
    let offsetY: number;

    if (containerAspect > videoAspect) {
      // Pillarbox (black bars on left/right)
      renderedH = containerH;
      renderedW = containerH * videoAspect;
      offsetX = (containerW - renderedW) / 2;
      offsetY = 0;
    } else {
      // Letterbox (black bars on top/bottom)
      renderedW = containerW;
      renderedH = containerW / videoAspect;
      offsetX = 0;
      offsetY = (containerH - renderedH) / 2;
    }

    const isMirrored = facingMode === 'user';

    // Draw bounding boxes & telemetry tags
    tracks.forEach(track => {
      const [x1Norm, y1Norm, x2Norm, y2Norm] = track.bbox_xyxy_norm;

      let leftNorm = x1Norm;
      let rightNorm = x2Norm;

      // Symmetric coordinate inversion for front camera mirroring
      if (isMirrored) {
        leftNorm = 1.0 - x2Norm;
        rightNorm = 1.0 - x1Norm;
      }

      const x = offsetX + leftNorm * renderedW;
      const y = offsetY + y1Norm * renderedH;
      const w = Math.max(10, (rightNorm - leftNorm) * renderedW);
      const h = Math.max(10, (y2Norm - y1Norm) * renderedH);

      const style = STATUS_STYLES[track.status] || STATUS_STYLES.POSE_UNAVAILABLE;
      const isReview = track.status === 'REVIEW';

      // 1. Draw Bounding Box Rectangle
      ctx.save();
      ctx.strokeStyle = style.color;
      ctx.lineWidth = isReview ? 3 : 2;
      ctx.fillStyle = style.bgColor;

      const radius = 6;
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, radius);
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      // 2. Format Status Label
      let statusText = STATUS_LABELS[track.status];
      if (track.status === 'CALIBRATING') {
        statusText = `Đang lấy mốc ${track.calibration_samples}/20`;
      } else if (track.status === 'OBSERVING' && track.turning_duration_ms) {
        const dur = (track.turning_duration_ms / 1000).toFixed(1);
        statusText = `Đang theo dõi (${dur}s)`;
      } else if (track.status === 'REVIEW' && track.reasons.length > 0) {
        statusText = `Nghi vấn: ${track.reasons.join(', ')}`;
      }

      const headerText = `ID ${track.track_id < 10 ? '0' : ''}${track.track_id} • ${statusText}`;

      // Measure text width
      ctx.font = '600 11px Inter, system-ui, sans-serif';
      const textMetrics = ctx.measureText(headerText);
      const tagH = 22;
      const tagW = Math.max(w, textMetrics.width + 16);
      const tagY = Math.max(4, y - tagH);

      // 3. Draw Header Pill Tag
      ctx.fillStyle = isReview ? '#dc2626' : 'rgba(15, 23, 42, 0.92)';
      ctx.beginPath();
      ctx.roundRect(x, tagY, tagW, tagH, [5, 5, 0, 0]);
      ctx.fill();

      // Tag Text
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'left';
      ctx.fillText(headerText, x + 8, tagY + 15);

      // 4. Bottom Telemetry Bar (for calibrated candidates)
      if (track.status !== 'CALIBRATING' && track.status !== 'POSE_UNAVAILABLE') {
        const botH = 18;
        const botY = y + h + 2;
        if (botY + botH <= containerH) {
          ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
          ctx.beginPath();
          ctx.roundRect(x, botY, Math.max(w, 136), botH, [0, 0, 4, 4]);
          ctx.fill();

          ctx.font = '600 10px JetBrains Mono, monospace';
          ctx.fillStyle = style.color;
          const yawSign = (track.yaw_delta_deg || 0) > 0 ? '+' : '';
          const line = `ΔYaw: ${yawSign}${track.yaw_delta_deg || 0}° | Hạ: ${((track.nose_drop_ratio || 0) * 100).toFixed(0)}%`;
          ctx.fillText(line, x + 6, botY + 13);
        }
      }
    });

  }, [tracks, videoDimensions, facingMode]);

  return (
    <canvas 
      ref={canvasRef} 
      className="absolute inset-0 w-full h-full pointer-events-none z-10"
    />
  );
};
