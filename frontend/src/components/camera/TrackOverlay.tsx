import React, { useEffect, useRef } from 'react';
import { TrackResult, CameraFacingMode, TrackStatus } from '../../types/monitoring';
import { STATUS_STYLES, STATUS_LABELS } from '../../constants/config';

interface TrackOverlayProps {
  tracks: TrackResult[];
  videoDimensions: { width: number; height: number };
  facingMode: CameraFacingMode;
}

interface SmoothTrackState {
  currentX: number;
  currentY: number;
  currentW: number;
  currentH: number;
  targetX: number;
  targetY: number;
  targetW: number;
  targetH: number;
  currentYaw: number;
  targetYaw: number;
  currentNoseDrop: number;
  targetNoseDrop: number;
  status: TrackStatus;
  reasons: string[];
  calibrationSamples: number;
  turningDurationMs: number;
  opacity: number;
  lastUpdatedMs: number;
}

export const TrackOverlay: React.FC<TrackOverlayProps> = ({
  tracks,
  videoDimensions,
  facingMode
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const smoothTracksRef = useRef<Map<number, SmoothTrackState>>(new Map());
  const tracksRef = useRef<TrackResult[]>(tracks);
  const facingModeRef = useRef<CameraFacingMode>(facingMode);
  const videoDimensionsRef = useRef(videoDimensions);
  const animFrameIdRef = useRef<number | null>(null);

  // Keep latest props in refs for animation loop
  tracksRef.current = tracks;
  facingModeRef.current = facingMode;
  videoDimensionsRef.current = videoDimensions;

  // Update target coordinates when new tracks arrive from WebSocket
  useEffect(() => {
    const now = performance.now();
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const containerW = rect.width;
    const containerH = rect.height;
    if (containerW === 0 || containerH === 0) return;

    const vW = videoDimensions.width > 0 ? videoDimensions.width : 640;
    const vH = videoDimensions.height > 0 ? videoDimensions.height : 480;

    const videoAspect = vW / vH;
    const containerAspect = containerW / containerH;

    let renderedW: number;
    let renderedH: number;
    let offsetX: number;
    let offsetY: number;

    if (containerAspect > videoAspect) {
      renderedH = containerH;
      renderedW = containerH * videoAspect;
      offsetX = (containerW - renderedW) / 2;
      offsetY = 0;
    } else {
      renderedW = containerW;
      renderedH = containerW / videoAspect;
      offsetX = 0;
      offsetY = (containerH - renderedH) / 2;
    }

    const isMirrored = facingMode === 'user';
    const activeIds = new Set<number>();

    tracks.forEach(track => {
      activeIds.add(track.track_id);
      const [x1Norm, y1Norm, x2Norm, y2Norm] = track.bbox_xyxy_norm;

      let leftNorm = x1Norm;
      let rightNorm = x2Norm;

      if (isMirrored) {
        leftNorm = 1.0 - x2Norm;
        rightNorm = 1.0 - x1Norm;
      }

      const tX = offsetX + leftNorm * renderedW;
      const tY = offsetY + y1Norm * renderedH;
      const tW = Math.max(16, (rightNorm - leftNorm) * renderedW);
      const tH = Math.max(16, (y2Norm - y1Norm) * renderedH);

      const existing = smoothTracksRef.current.get(track.track_id);
      if (existing) {
        existing.targetX = tX;
        existing.targetY = tY;
        existing.targetW = tW;
        existing.targetH = tH;
        existing.targetYaw = track.yaw_delta_deg || 0;
        existing.targetNoseDrop = track.nose_drop_ratio || 0;
        existing.status = track.status;
        existing.reasons = track.reasons;
        existing.calibrationSamples = track.calibration_samples;
        existing.turningDurationMs = track.turning_duration_ms || 0;
        existing.lastUpdatedMs = now;
      } else {
        smoothTracksRef.current.set(track.track_id, {
          currentX: tX,
          currentY: tY,
          currentW: tW,
          currentH: tH,
          targetX: tX,
          targetY: tY,
          targetW: tW,
          targetH: tH,
          currentYaw: track.yaw_delta_deg || 0,
          targetYaw: track.yaw_delta_deg || 0,
          currentNoseDrop: track.nose_drop_ratio || 0,
          targetNoseDrop: track.nose_drop_ratio || 0,
          status: track.status,
          reasons: track.reasons,
          calibrationSamples: track.calibration_samples,
          turningDurationMs: track.turning_duration_ms || 0,
          opacity: 0.1,
          lastUpdatedMs: now
        });
      }
    });

  }, [tracks, videoDimensions, facingMode]);

  // 60 FPS RequestAnimationFrame Render Loop with LERP Interpolation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const renderLoop = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;

      if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, rect.width, rect.height);

      const smoothMap = smoothTracksRef.current;
      const now = performance.now();

      // Prune inactive tracks
      for (const [id, st] of smoothMap.entries()) {
        const isStale = now - st.lastUpdatedMs > 750;
        if (isStale) {
          st.opacity -= 0.08;
          if (st.opacity <= 0) {
            smoothMap.delete(id);
            continue;
          }
        } else {
          st.opacity = Math.min(1.0, st.opacity + 0.15);
        }

        // LERP Smooth Interpolation (0.32 factor for snappy 60fps tracking)
        const lerpFactor = 0.32;
        st.currentX += (st.targetX - st.currentX) * lerpFactor;
        st.currentY += (st.targetY - st.currentY) * lerpFactor;
        st.currentW += (st.targetW - st.currentW) * lerpFactor;
        st.currentH += (st.targetH - st.currentH) * lerpFactor;
        st.currentYaw += (st.targetYaw - st.currentYaw) * lerpFactor;
        st.currentNoseDrop += (st.targetNoseDrop - st.currentNoseDrop) * lerpFactor;

        const x = st.currentX;
        const y = st.currentY;
        const w = st.currentW;
        const h = st.currentH;
        const style = STATUS_STYLES[st.status] || STATUS_STYLES.POSE_UNAVAILABLE;
        const isReview = st.status === 'REVIEW';
        const isObserving = st.status === 'OBSERVING';

        ctx.globalAlpha = st.opacity;

        // 1. Sleek Gradient Fill inside Bounding Box
        const grad = ctx.createLinearGradient(x, y, x, y + h);
        if (isReview) {
          grad.addColorStop(0, 'rgba(239, 68, 68, 0.12)');
          grad.addColorStop(1, 'rgba(239, 68, 68, 0.02)');
        } else if (isObserving) {
          grad.addColorStop(0, 'rgba(245, 158, 11, 0.10)');
          grad.addColorStop(1, 'rgba(245, 158, 11, 0.01)');
        } else {
          grad.addColorStop(0, 'rgba(16, 185, 129, 0.08)');
          grad.addColorStop(1, 'rgba(16, 185, 129, 0.01)');
        }
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 6);
        ctx.fill();

        // 2. Base Border
        ctx.strokeStyle = isReview 
          ? 'rgba(239, 68, 68, 0.65)' 
          : isObserving 
            ? 'rgba(245, 158, 11, 0.55)' 
            : 'rgba(16, 185, 129, 0.45)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // 3. Cyberpunk High-Tech Corner Brackets
        const cornerLen = Math.min(20, w * 0.25, h * 0.25);
        ctx.save();
        ctx.strokeStyle = style.color;
        ctx.lineWidth = isReview ? 3.5 : 2.5;
        ctx.shadowColor = style.color;
        ctx.shadowBlur = isReview ? 10 : 6;

        // Top-Left ┏
        ctx.beginPath();
        ctx.moveTo(x, y + cornerLen);
        ctx.lineTo(x, y);
        ctx.lineTo(x + cornerLen, y);
        ctx.stroke();

        // Top-Right ┓
        ctx.beginPath();
        ctx.moveTo(x + w - cornerLen, y);
        ctx.lineTo(x + w, y);
        ctx.lineTo(x + w, y + cornerLen);
        ctx.stroke();

        // Bottom-Left ┗
        ctx.beginPath();
        ctx.moveTo(x, y + h - cornerLen);
        ctx.lineTo(x, y + h);
        ctx.lineTo(x + cornerLen, y + h);
        ctx.stroke();

        // Bottom-Right ┛
        ctx.beginPath();
        ctx.moveTo(x + w - cornerLen, y + h);
        ctx.lineTo(x + w, y + h);
        ctx.lineTo(x + w, y + h - cornerLen);
        ctx.stroke();
        ctx.restore();

        // 4. Subtle Head Area Crosshair Reticle
        const headCenterY = y + h * 0.26;
        const headCenterX = x + w * 0.5;
        ctx.save();
        ctx.strokeStyle = isReview ? 'rgba(239, 68, 68, 0.45)' : 'rgba(56, 189, 248, 0.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(headCenterX - 8, headCenterY);
        ctx.lineTo(headCenterX + 8, headCenterY);
        ctx.moveTo(headCenterX, headCenterY - 8);
        ctx.lineTo(headCenterX, headCenterY + 8);
        ctx.stroke();
        ctx.restore();

        // 5. Header Pill Tag (ID & Status Text)
        let statusText = STATUS_LABELS[st.status];
        if (st.status === 'CALIBRATING') {
          statusText = `Hiệu chuẩn ${st.calibrationSamples}/20`;
        } else if (st.status === 'OBSERVING') {
          const s = (st.turningDurationMs / 1000).toFixed(1);
          statusText = `Theo dõi (${s}s)`;
        } else if (st.status === 'REVIEW') {
          statusText = st.reasons.length > 0 
            ? `NGHI VẤN: ${st.reasons.join(', ')}` 
            : 'NGHI VẤN VI PHẠM';
        }

        const tagText = `ID ${id < 10 ? '0' : ''}${id}  •  ${statusText}`;
        ctx.font = '700 11px Inter, system-ui, sans-serif';
        const textMetrics = ctx.measureText(tagText);
        const tagH = 22;
        const tagW = Math.max(w, textMetrics.width + 18);
        const tagY = Math.max(6, y - tagH - 2);

        // Header Pill Background
        ctx.save();
        ctx.fillStyle = isReview 
          ? 'rgba(220, 38, 38, 0.95)' 
          : isObserving
            ? 'rgba(217, 119, 6, 0.92)'
            : 'rgba(15, 23, 42, 0.92)';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
        ctx.shadowBlur = 4;
        ctx.beginPath();
        ctx.roundRect(x, tagY, tagW, tagH, 5);
        ctx.fill();

        // Status Indicator Dot
        ctx.fillStyle = isReview ? '#fee2e2' : style.color;
        ctx.beginPath();
        ctx.arc(x + 9, tagY + tagH / 2, 3.5, 0, Math.PI * 2);
        ctx.fill();

        // Text
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';
        ctx.fillText(tagText, x + 18, tagY + 15);
        ctx.restore();

        // 6. Bottom Telemetry Bar with Yaw Gauge (if Calibrated)
        if (st.status !== 'CALIBRATING' && st.status !== 'POSE_UNAVAILABLE') {
          const botH = 22;
          const botY = y + h + 4;
          const barW = Math.max(w, 150);

          if (botY + botH <= rect.height) {
            ctx.save();
            ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
            ctx.strokeStyle = 'rgba(51, 65, 85, 0.8)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(x, botY, barW, botH, 5);
            ctx.fill();
            ctx.stroke();

            // Yaw Delta & Nose Drop Metrics
            ctx.font = '600 10px JetBrains Mono, Menlo, monospace';
            const yawVal = Math.round(st.currentYaw);
            const yawSign = yawVal > 0 ? '+' : '';
            const noseDropVal = Math.round(st.currentNoseDrop * 100);

            // Left side text: Yaw Angle
            ctx.fillStyle = Math.abs(yawVal) > 35 ? '#f87171' : '#38bdf8';
            ctx.fillText(`ΔYaw: ${yawSign}${yawVal}°`, x + 7, botY + 15);

            // Right side text: Nose Drop
            ctx.fillStyle = noseDropVal > 15 ? '#f87171' : '#a7f3d0';
            ctx.fillText(`Hạ: ${noseDropVal}%`, x + 82, botY + 15);

            // Direction arrow indicator
            if (Math.abs(yawVal) > 10) {
              const arrow = yawVal > 0 ? '▶' : '◀';
              ctx.fillStyle = Math.abs(yawVal) > 35 ? '#ef4444' : '#fbbf24';
              ctx.fillText(arrow, x + barW - 14, botY + 15);
            }
            ctx.restore();
          }
        }
      }

      ctx.restore();
      animFrameIdRef.current = requestAnimationFrame(renderLoop);
    };

    animFrameIdRef.current = requestAnimationFrame(renderLoop);

    return () => {
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
    };
  }, []);

  return (
    <canvas 
      ref={canvasRef} 
      className="absolute inset-0 w-full h-full pointer-events-none z-10"
    />
  );
};
