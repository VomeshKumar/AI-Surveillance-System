import cv2
import numpy as np
import logging
import os
from typing import Tuple, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class YuNetDetector:
    """Wrapper for ONNX YuNet face detection model."""
    
    def __init__(self, model_path: str = None):
        if model_path is None:
            model_path = os.path.join(settings.ARTIFACTS_DIR, "yunet.onnx")
            
        self.model_path = model_path
        self.detector = None
        self._load_model()
        
    def _load_model(self):
        if not os.path.exists(self.model_path):
            logger.error(f"YuNet model not found at {self.model_path}. Please download it.")
            return
            
        # OpenCV DNN backend using ONNX uses all threads by default.
        # Set OpenCV threads to avoid starving the system.
        cv2.setNumThreads(2)
        
        # Initialize YuNet. Input size is set dynamically per frame during inference.
        self.detector = cv2.FaceDetectorYN.create(
            model=self.model_path,
            config="",
            input_size=(320, 320),
            score_threshold=settings.DETECTION_THRESHOLD,
            nms_threshold=0.3,
            top_k=50
        )
        logger.info(f"Loaded YuNet from {self.model_path}")
        
    def detect(self, frame: np.ndarray) -> List[np.ndarray]:
        """
        Detect faces in a frame.
        Returns a numpy array of faces where each face is:
        [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
        """
        if self.detector is None:
            return []
            
        h, w, _ = frame.shape
        self.detector.setInputSize((w, h))
        
        # YuNet expects BGR images natively
        _, faces = self.detector.detect(frame)
        
        if faces is None:
            return []
            
        return faces
