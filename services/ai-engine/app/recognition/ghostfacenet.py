import cv2
import numpy as np
import onnxruntime as ort
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class GhostFaceNet:
    """Wrapper for ONNX GhostFaceNet model for embedding generation."""
    
    def __init__(self, model_path: str = None):
        if model_path is None:
            model_path = os.path.join(settings.ARTIFACTS_DIR, "ghostfacenet.onnx")
            
        self.model_path = model_path
        self.session = None
        self._load_model()
        
    def _load_model(self):
        if not os.path.exists(self.model_path):
            logger.error(f"GhostFaceNet model not found at {self.model_path}")
            return
            
        # Limit ONNX threads so it doesn't starve the camera reading thread causing micro-pauses
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 2
        sess_options.inter_op_num_threads = 1
        
        # Using CPU for widespread compatibility. Will be blazing fast with quantization
        self.session = ort.InferenceSession(self.model_path, sess_options=sess_options, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        logger.info(f"Loaded GhostFaceNet from {self.model_path} with limited threads")
        
    def get_embedding(self, aligned_face: np.ndarray) -> np.ndarray:
        """
        Generate a 512D embedding for a 112x112 aligned face crop.
        """
        if self.session is None or aligned_face is None:
            return np.zeros((512,), dtype=np.float32)
            
        # Preprocessing: Convert BGR to RGB, scale to [-1, 1]
        blob = cv2.dnn.blobFromImage(
            aligned_face, 
            1.0 / 127.5, 
            (112, 112), 
            (127.5, 127.5, 127.5), 
            swapRB=True
        )
        
        # OpenCV's blobFromImage returns (N, C, H, W). 
        # GhostFaceNet (Keras-based ONNX) expects (N, H, W, C).
        blob = np.transpose(blob, (0, 2, 3, 1))
        
        # Inference
        embedding = self.session.run(None, {self.input_name: blob})[0][0]
        
        # L2 Normalization to ensure cosine similarity calculation is just a dot product
        embedding = embedding / np.linalg.norm(embedding)
        return embedding
