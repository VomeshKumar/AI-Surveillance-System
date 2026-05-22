import cv2
import numpy as np

# Standard reference facial points for 112x112 crops (ArcFace format)
REFERENCE_FACIAL_POINTS = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041]
], dtype=np.float32)

def align_face(img: np.ndarray, landmarks: np.ndarray, output_size=(112, 112)) -> np.ndarray:
    """
    Aligns a face based on 5 facial landmarks using an affine transformation.
    img: The original frame
    landmarks: shape (5, 2) array of coordinates (left_eye, right_eye, nose, left_mouth, right_mouth)
    """
    # Estimate affine transform matrix
    M, _ = cv2.estimateAffinePartial2D(landmarks, REFERENCE_FACIAL_POINTS)
    
    if M is None:
        return None
        
    aligned_face = cv2.warpAffine(img, M, output_size, borderValue=0.0)
    return aligned_face
