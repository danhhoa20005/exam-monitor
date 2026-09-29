"""
Head Pose Estimation using SolvePnP (EPNP + ITERATIVE).
Calculates Euler angles (Yaw, Pitch, Roll) in degrees from 2D facial keypoints.
"""
from __future__ import annotations

import math
try:
    import numpy as np
    import cv2
    MODEL_POINTS_3D = np.array([
        [0.0, 0.0, 0.0],          # Nose tip
        [0.0, -330.0, -65.0],     # Chin
        [-225.0, 170.0, -135.0],  # Left eye outer corner
        [225.0, 170.0, -135.0],   # Right eye outer corner
        [-150.0, -150.0, -125.0], # Left mouth corner
        [150.0, -150.0, -125.0]   # Right mouth corner
    ], dtype=np.float64)
except ImportError:
    np = None
    cv2 = None
    MODEL_POINTS_3D = None

from typing import Any

def estimate_head_pose_pnp(
    image_points_2d: Any,
    frame_width: int,
    frame_height: int
) -> tuple[float, float, float] | None:
    """
    Estimate head orientation (yaw, pitch, roll) in degrees.
    
    Args:
        image_points_2d: (6, 2) array of 2D coordinates in full frame.
        frame_width: Frame width in pixels.
        frame_height: Frame height in pixels.
        
    Returns:
        (yaw, pitch, roll) in degrees, or None if estimation fails.
    """
    if image_points_2d.shape != (6, 2):
        return None

    # Approximate camera intrinsics matrix
    focal_length = frame_width
    center = (frame_width / 2.0, frame_height / 2.0)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float64)

    dist_coeffs = np.zeros((4, 1), dtype=np.float64)  # Assuming no lens distortion

    try:
        # Step 1: Initial coarse estimate with EPNP
        success, rvec, tvec = cv2.solvePnP(
            MODEL_POINTS_3D,
            image_points_2d,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_EPNP
        )

        if not success:
            # Fallback to standard iterative
            success, rvec, tvec = cv2.solvePnP(
                MODEL_POINTS_3D,
                image_points_2d,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )

        if not success or rvec is None:
            return None

        # Step 2: Refine with ITERATIVE
        success, rvec, tvec = cv2.solvePnP(
            MODEL_POINTS_3D,
            image_points_2d,
            camera_matrix,
            dist_coeffs,
            rvec=rvec,
            tvec=tvec,
            useExtrinsicGuess=True,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success or rvec is None:
            return None

        # Convert rotation vector to rotation matrix
        rmat, _ = cv2.Rodrigues(rvec)

        # Decompose rotation matrix into Euler angles
        sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
        singular = sy < 1e-6

        if not singular:
            pitch = math.atan2(rmat[2, 1], rmat[2, 2])
            yaw = math.atan2(-rmat[2, 0], sy)
            roll = math.atan2(rmat[1, 0], rmat[0, 0])
        else:
            pitch = math.atan2(-rmat[1, 2], rmat[1, 1])
            yaw = math.atan2(-rmat[2, 0], sy)
            roll = 0.0

        # Convert radians to degrees
        yaw_deg = math.degrees(yaw)
        pitch_deg = math.degrees(pitch)
        roll_deg = math.degrees(roll)

        return (round(yaw_deg, 2), round(pitch_deg, 2), round(roll_deg, 2))

    except Exception:
        return None

def compute_delta_yaw(current_yaw: float, baseline_yaw: float) -> float:
    """
    Calculate minimal angular deviation between current yaw and baseline.
    delta_yaw = ((yaw - yaw_0 + 180) % 360) - 180
    """
    return ((current_yaw - baseline_yaw + 180.0) % 360.0) - 180.0
