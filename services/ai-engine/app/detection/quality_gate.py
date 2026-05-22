import numpy as np

def estimate_face_pose_from_landmarks(landmarks_5pt):
    """
    Estimates the yaw and pitch of a face based on 5-point landmarks.
    landmarks_5pt: [[x1,y1], [x2,y2], [nose_x,nose_y], [mouth_left], [mouth_right]]
    Returns: (yaw_degrees, pitch_degrees) - absolute values
    """
    # YuNet landmarks: left_eye, right_eye, nose, left_mouth_corner, right_mouth_corner
    left_eye = np.array(landmarks_5pt[0], dtype=np.float32)
    right_eye = np.array(landmarks_5pt[1], dtype=np.float32)
    nose = np.array(landmarks_5pt[2], dtype=np.float32)
    
    # Calculate dynamic reference distance (inter-ocular distance)
    iod = np.linalg.norm(left_eye - right_eye)
    if iod == 0:
        iod = 1.0  # Prevent division by zero
        
    # [NEW] Damping for small faces: If face is distant (IOD < 25), slight pixel jitter 
    # creates huge fake angles. We artificially boost IOD in the formula to dampen this.
    effective_iod = iod
    if iod < 25:
        effective_iod = iod * (1.0 + (25 - iod) / 25.0)
        
    eye_center = (left_eye + right_eye) / 2.0
    
    # YAW: horizontal angle (head turn left/right)
    nose_to_eye_x = nose[0] - eye_center[0]
    # Increased divisor to 1.2 to be less sensitive
    yaw_rad = np.arctan2(abs(nose_to_eye_x), effective_iod * 1.2) 
    yaw_deg = abs(np.degrees(yaw_rad))
    
    # PITCH: vertical angle (head tilt up/down)
    # Note: Nose is naturally below eye center, we need to subtract the 'natural' offset
    natural_pitch_offset = iod * 0.4 
    nose_to_eye_y_adjusted = abs(nose[1] - eye_center[1]) - natural_pitch_offset
    nose_to_eye_y_adjusted = max(0, nose_to_eye_y_adjusted)
    
    # Increased divisor to 1.0 to be less sensitive
    pitch_rad = np.arctan2(nose_to_eye_y_adjusted, effective_iod * 1.0) 
    pitch_deg = abs(np.degrees(pitch_rad))
    
    return yaw_deg, pitch_deg

def dynamic_threshold_from_pose(yaw_deg, pitch_deg, base_threshold=0.40):
    """
    Returns adjusted threshold OR None if face is too extreme.
    base_threshold: the normal confidence threshold (e.g., 0.40)
    """
    max_angle = max(yaw_deg, pitch_deg)
    
    if max_angle < 25:
        return base_threshold  # Frontal: 0.40
    elif max_angle < 45:
        return base_threshold + 0.05  # Slight angle: 0.45
    elif max_angle < 65:
        return base_threshold + 0.10  # Profile: 0.50
    else:
        return None  # Extreme: Skip matching to avoid False Positives
