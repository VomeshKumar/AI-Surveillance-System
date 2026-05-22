import faiss
import numpy as np
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class WatchlistIndex:
    """In-memory HNSW vector index for high-speed face recognition matching."""
    
    def __init__(self, d=512):
        self.d = d
        self.index_path = os.path.join(os.path.dirname(settings.ARTIFACTS_DIR), "faiss", "watchlist.index")
        self.index = None
        self.last_mtime = 0
        self._init_index()
        
    def _init_index(self):
        # We use IndexHNSWFlat for fast approximate nearest neighbors
        # Inner Product (METRIC_INNER_PRODUCT) works as Cosine Similarity because vectors are L2 normalized
        base_index = faiss.IndexHNSWFlat(self.d, 32, faiss.METRIC_INNER_PRODUCT)
        base_index.hnsw.efSearch = 64
        self.index = faiss.IndexIDMap(base_index)
        
        if os.path.exists(self.index_path):
            try:
                self.index = faiss.read_index(self.index_path)
                self.last_mtime = os.path.getmtime(self.index_path)
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors from {self.index_path}")
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}. Starting fresh.")
                
    def check_for_updates(self) -> bool:
        """Hot-reloads the FAISS index if the file on disk has changed. Returns True if reloaded."""
        if os.path.exists(self.index_path):
            current_mtime = os.path.getmtime(self.index_path)
            # Add a small buffer to prevent reloading while writing
            if current_mtime > self.last_mtime + 0.1:
                logger.info("Detected changes in FAISS index file. Hot-reloading...")
                self._init_index()
                return True
        return False
                
    def save(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        logger.info(f"Saved FAISS index to {self.index_path}")
        
    def add_faces(self, embeddings: np.ndarray, person_ids: np.ndarray):
        """Add face embeddings to the index."""
        if len(embeddings) == 0:
            return
            
        self.index.add_with_ids(embeddings, person_ids)
        self.save()
        
    def search(self, query_embeddings: np.ndarray, k=1, threshold=0.65) -> list:
        """Search for matches above a given threshold."""
        if self.index.ntotal == 0 or len(query_embeddings) == 0:
            return [[] for _ in range(len(query_embeddings))]
            
        distances, indices = self.index.search(query_embeddings, k)
        
        results = []
        for i in range(len(query_embeddings)):
            matches = []
            for j in range(k):
                if distances[i][j] >= threshold and indices[i][j] != -1:
                    matches.append({
                        "person_id": int(indices[i][j]),
                        "confidence": float(distances[i][j])
                    })
            results.append(matches)
            
        return results
