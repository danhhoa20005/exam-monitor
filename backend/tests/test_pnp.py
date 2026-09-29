"""
Unit tests for PnP 3D head pose estimation and angular math.
"""
try:
    import numpy as np
except ImportError:
    np = None
from app.inference.pnp_head_pose import compute_delta_yaw, estimate_head_pose_pnp

def test_compute_delta_yaw():
    # Normal minimal deviation
    assert compute_delta_yaw(10.0, 0.0) == 10.0
    assert compute_delta_yaw(-15.0, 0.0) == -15.0
    
    # Crossing 180/-180 wrap-around boundary
    assert compute_delta_yaw(175.0, -175.0) == -10.0
    assert compute_delta_yaw(-175.0, 175.0) == 10.0
    assert compute_delta_yaw(350.0, 10.0) == -20.0

def test_pnp_geometry():
    # 6 points on a 640x480 frame facing forward
    points_2d = np.array([
        [320.0, 240.0],  # Nose
        [320.0, 310.0],  # Chin
        [270.0, 210.0],  # Left eye
        [370.0, 210.0],  # Right eye
        [290.0, 280.0],  # Left mouth
        [350.0, 280.0]   # Right mouth
    ], dtype=np.float64)

    result = estimate_head_pose_pnp(points_2d, 640, 480)
    assert result is not None
    yaw, pitch, roll = result
    assert isinstance(yaw, float)
    assert isinstance(pitch, float)
    assert isinstance(roll, float)
