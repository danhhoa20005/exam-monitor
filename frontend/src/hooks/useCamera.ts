import { useState, useRef, useCallback, useEffect } from 'react';
import { CameraFacingMode } from '../types/monitoring';

export interface CameraError {
  type: 'PERMISSION_DENIED' | 'NOT_FOUND' | 'IN_USE' | 'NOT_SUPPORTED' | 'UNKNOWN';
  message: string;
}

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const offscreenCanvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [facingMode, setFacingMode] = useState<CameraFacingMode>('environment');
  const [error, setError] = useState<CameraError | null>(null);
  const [videoDimensions, setVideoDimensions] = useState<{ width: number; height: number }>({ width: 0, height: 0 });

  // Stop all active media tracks completely
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop();
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  }, []);

  // Start Camera with specified facing mode
  const startCamera = useCallback(async (modeToUse?: CameraFacingMode) => {
    setError(null);
    const targetMode = modeToUse || facingMode;

    // Check browser support for getUserMedia
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const err: CameraError = {
        type: 'NOT_SUPPORTED',
        message: 'Trình duyệt hiện tại không hỗ trợ truy cập Camera (getUserMedia).'
      };
      setError(err);
      return false;
    }

    // Stop existing stream if any before acquiring a new one
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }

    try {
      let stream: MediaStream;
      try {
        // First try with preferred facingMode
        const constraints: MediaStreamConstraints = {
          video: {
            facingMode: { ideal: targetMode },
            width: { ideal: 1280 },
            height: { ideal: 720 }
          },
          audio: false
        };
        stream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (firstErr: unknown) {
        // If preferred facingMode (e.g. environment) failed, fallback to any available video camera
        console.warn('Fallback to basic video constraint:', firstErr);
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.setAttribute('playsinline', 'true');
        videoRef.current.setAttribute('autoplay', 'true');
        videoRef.current.muted = true;
        
        // Wait for video metadata to load dimensions
        await new Promise<void>((resolve) => {
          if (!videoRef.current) return resolve();
          videoRef.current.onloadedmetadata = () => {
            if (videoRef.current) {
              setVideoDimensions({
                width: videoRef.current.videoWidth,
                height: videoRef.current.videoHeight
              });
            }
            resolve();
          };
        });

        await videoRef.current.play();
      }

      setFacingMode(targetMode);
      setIsStreaming(true);
      return true;

    } catch (err: unknown) {
      let camError: CameraError;
      const errorObj = err as { name?: string; message?: string };

      if (errorObj.name === 'NotAllowedError' || errorObj.name === 'PermissionDeniedError') {
        camError = {
          type: 'PERMISSION_DENIED',
          message: 'Bạn đã từ chối quyền truy cập camera. Vui lòng cho phép quyền camera trong cài đặt trình duyệt để tiếp tục.'
        };
      } else if (errorObj.name === 'NotFoundError' || errorObj.name === 'DevicesNotFoundError') {
        camError = {
          type: 'NOT_FOUND',
          message: 'Không tìm thấy thiết bị camera trên máy của bạn.'
        };
      } else if (errorObj.name === 'NotReadableError' || errorObj.name === 'TrackStartError') {
        camError = {
          type: 'IN_USE',
          message: 'Camera đang bị ứng dụng khác sử dụng hoặc bị khóa bởi hệ thống.'
        };
      } else {
        camError = {
          type: 'UNKNOWN',
          message: errorObj.message || 'Lỗi không xác định khi mở camera.'
        };
      }

      setError(camError);
      setIsStreaming(false);
      return false;
    }
  }, [facingMode]);

  // Toggle Front / Back Camera
  const toggleCamera = useCallback(async () => {
    if (!isStreaming) return;
    const nextMode: CameraFacingMode = facingMode === 'environment' ? 'user' : 'environment';
    await startCamera(nextMode);
  }, [isStreaming, facingMode, startCamera]);

  // Capture single frame to Base64 JPEG (640x480 or current aspect ratio, quality 0.75)
  const captureFrame = useCallback((targetWidth: number = 640, targetHeight: number = 480): { base64: string; width: number; height: number } | null => {
    const video = videoRef.current;
    if (!video || !isStreaming || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null;
    }

    if (!offscreenCanvasRef.current) {
      offscreenCanvasRef.current = document.createElement('canvas');
    }
    const canvas = offscreenCanvasRef.current;
    canvas.width = targetWidth;
    canvas.height = targetHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0, targetWidth, targetHeight);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.75);
    const base64 = dataUrl.split(',')[1] || '';

    return { base64, width: targetWidth, height: targetHeight };
  }, [isStreaming]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  return {
    videoRef,
    isStreaming,
    facingMode,
    error,
    videoDimensions,
    startCamera,
    stopCamera,
    toggleCamera,
    captureFrame
  };
}
