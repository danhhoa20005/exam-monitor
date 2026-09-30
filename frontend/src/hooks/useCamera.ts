import { useState, useRef, useCallback, useEffect } from 'react';
import { CameraFacingMode } from '../types/monitoring';

export interface CameraError {
  type: 'PERMISSION_DENIED' | 'NOT_FOUND' | 'IN_USE' | 'NOT_SUPPORTED' | 'UNKNOWN';
  message: string;
}

export interface VideoDevice {
  deviceId: string;
  label: string;
  facing: CameraFacingMode;
}

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const offscreenCanvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [facingMode, setFacingMode] = useState<CameraFacingMode>('environment');
  const [activeDeviceId, setActiveDeviceId] = useState<string>('');
  const [activeCameraLabel, setActiveCameraLabel] = useState<string>('Camera Sau');
  const [availableDevices, setAvailableDevices] = useState<VideoDevice[]>([]);
  const [error, setError] = useState<CameraError | null>(null);
  const [videoDimensions, setVideoDimensions] = useState<{ width: number; height: number }>({ width: 0, height: 0 });

  // Enumerate all video input devices and detect facing direction
  const refreshDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoInputs = devices.filter(d => d.kind === 'videoinput');
      
      const parsed: VideoDevice[] = videoInputs.map((d, index) => {
        const labelLower = d.label.toLowerCase();
        let facing: CameraFacingMode = 'environment';
        
        if (
          labelLower.includes('front') || 
          labelLower.includes('user') || 
          labelLower.includes('trước') || 
          labelLower.includes('facetime') ||
          labelLower.includes('selfie')
        ) {
          facing = 'user';
        } else if (
          labelLower.includes('back') || 
          labelLower.includes('rear') || 
          labelLower.includes('sau') || 
          labelLower.includes('environment') ||
          labelLower.includes('chính')
        ) {
          facing = 'environment';
        } else {
          // If ambiguous, first device is often environment/webcam
          facing = index === 0 ? 'environment' : 'user';
        }

        const fallbackLabel = facing === 'environment' 
          ? `Camera Sau ${index > 0 ? `#${index + 1}` : ''}` 
          : `Camera Trước ${index > 0 ? `#${index + 1}` : ''}`;
        const cleanLabel = d.label ? d.label : fallbackLabel;

        return {
          deviceId: d.deviceId,
          label: cleanLabel,
          facing
        };
      });

      setAvailableDevices(parsed);
    } catch (err) {
      console.warn('Không thể liệt kê thiết bị camera:', err);
    }
  }, []);

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
    setVideoDimensions({ width: 0, height: 0 });
  }, []);

  // Start Camera with specified facing mode or specific deviceId
  const startCamera = useCallback(async (modeToUse?: CameraFacingMode, specificDeviceId?: string) => {
    setError(null);
    const targetMode = modeToUse || facingMode;

    // Check browser support for getUserMedia
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const err: CameraError = {
        type: 'NOT_SUPPORTED',
        message: 'Trình duyệt hiện tại không hỗ trợ truy cập Camera (getUserMedia). Vui lòng dùng Chrome hoặc Safari mới nhất.'
      };
      setError(err);
      return false;
    }

    // Stop existing stream before acquiring a new one
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }

    try {
      let stream: MediaStream;

      if (specificDeviceId) {
        // Exact device constraint
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            deviceId: { exact: specificDeviceId },
            width: { ideal: 1280 },
            height: { ideal: 720 }
          },
          audio: false
        });
      } else {
        try {
          // Preferred facingMode constraint (environment = rear camera priority)
          stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: { ideal: targetMode },
              width: { ideal: 1280 },
              height: { ideal: 720 }
            },
            audio: false
          });
        } catch (firstErr: unknown) {
          // Fallback to basic constraint if exact facing mode fails
          console.warn('Fallback to basic video constraint:', firstErr);
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        }
      }

      streamRef.current = stream;

      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        const trackSettings = videoTrack.getSettings();
        let detectedFacing = (trackSettings.facingMode as CameraFacingMode) || targetMode;
        
        // Fallback detection from track label if facingMode is not provided in settings
        const labelLower = (videoTrack.label || '').toLowerCase();
        if (labelLower.includes('front') || labelLower.includes('user') || labelLower.includes('trước') || labelLower.includes('facetime')) {
          detectedFacing = 'user';
        } else if (labelLower.includes('back') || labelLower.includes('rear') || labelLower.includes('sau') || labelLower.includes('environment')) {
          detectedFacing = 'environment';
        }

        setFacingMode(detectedFacing);
        setActiveDeviceId(trackSettings.deviceId || '');
        
        const friendlyLabel = videoTrack.label 
          ? `${detectedFacing === 'environment' ? 'Camera Sau' : 'Camera Trước'} (${videoTrack.label})`
          : (detectedFacing === 'environment' ? 'Camera Sau (Mặc định)' : 'Camera Trước (Selfie)');
        
        setActiveCameraLabel(friendlyLabel);
      }

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
                width: videoRef.current.videoWidth || 1280,
                height: videoRef.current.videoHeight || 720
              });
            }
            resolve();
          };
        });

        await videoRef.current.play();
      }

      setIsStreaming(true);
      await refreshDevices();
      return true;

    } catch (err: unknown) {
      let camError: CameraError;
      const errorObj = err as { name?: string; message?: string };

      if (errorObj.name === 'NotAllowedError' || errorObj.name === 'PermissionDeniedError') {
        camError = {
          type: 'PERMISSION_DENIED',
          message: 'Bạn đã từ chối quyền camera. Vui lòng cho phép quyền truy cập camera trong cài đặt trình duyệt để hệ thống hoạt động.'
        };
      } else if (errorObj.name === 'NotFoundError' || errorObj.name === 'DevicesNotFoundError') {
        camError = {
          type: 'NOT_FOUND',
          message: 'Không tìm thấy thiết bị camera trên thiết bị của bạn.'
        };
      } else if (errorObj.name === 'NotReadableError' || errorObj.name === 'TrackStartError') {
        camError = {
          type: 'IN_USE',
          message: 'Camera đang bị ứng dụng khác chiếm dụng hoặc bị khóa bởi hệ điều hành.'
        };
      } else {
        camError = {
          type: 'UNKNOWN',
          message: errorObj.message || 'Lỗi không xác định khi kích hoạt camera.'
        };
      }

      setError(camError);
      setIsStreaming(false);
      return false;
    }
  }, [facingMode, refreshDevices]);

  // Toggle Front / Back Camera
  const toggleCamera = useCallback(async () => {
    const nextMode: CameraFacingMode = facingMode === 'environment' ? 'user' : 'environment';
    await startCamera(nextMode);
  }, [facingMode, startCamera]);

  // Switch to specific device ID from dropdown
  const selectDevice = useCallback(async (deviceId: string) => {
    const dev = availableDevices.find(d => d.deviceId === deviceId);
    const mode = dev ? dev.facing : facingMode;
    await startCamera(mode, deviceId);
  }, [availableDevices, facingMode, startCamera]);

  // Capture single frame to Base64 JPEG with customizable resolution and quality
  const captureFrame = useCallback((
    targetWidth: number = 640, 
    targetHeight: number = 480, 
    quality: number = 0.75
  ): { base64: string; width: number; height: number; facingMode: CameraFacingMode } | null => {
    const video = videoRef.current;
    if (!video || !isStreaming || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null;
    }

    if (!offscreenCanvasRef.current) {
      offscreenCanvasRef.current = document.createElement('canvas');
    }
    const canvas = offscreenCanvasRef.current;
    if (canvas.width !== targetWidth) canvas.width = targetWidth;
    if (canvas.height !== targetHeight) canvas.height = targetHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0, targetWidth, targetHeight);
    const dataUrl = canvas.toDataURL('image/jpeg', quality);
    const base64 = dataUrl.split(',')[1] || '';

    return { 
      base64, 
      width: targetWidth, 
      height: targetHeight,
      facingMode 
    };
  }, [isStreaming, facingMode]);

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
    isFrontCamera: facingMode === 'user',
    isBackCamera: facingMode === 'environment',
    activeDeviceId,
    activeCameraLabel,
    availableDevices,
    error,
    videoDimensions,
    startCamera,
    stopCamera,
    toggleCamera,
    selectDevice,
    captureFrame
  };
}
