"""
ByteTrack: Robust multi-object tracker using Kalman Filter + Hungarian Algorithm.
Replaces CentroidTracker. Interface is compatible: update(faces) -> [(track_id, bbox)]
"""
import numpy as np
from scipy.optimize import linear_sum_assignment


# ---------------------------------------------------------------------------
# Kalman Filter for bounding box state [cx, cy, w, h, vcx, vcy, vw, vh]
# ---------------------------------------------------------------------------
class KalmanBoxFilter:
    """
    Constant-velocity Kalman Filter for a bounding box.
    State vector: [cx, cy, w, h, vcx, vcy, vw, vh]
    """
    def __init__(self, bbox):
        dt = 1.0  # time step (1 frame)
        # State transition matrix (8x8)
        self.F = np.eye(8)
        for i in range(4):
            self.F[i, i + 4] = dt

        # Measurement matrix (4x8) — we observe [cx, cy, w, h]
        self.H = np.eye(4, 8)

        # Process noise covariance
        self.Q = np.eye(8) * 1.0
        self.Q[4:, 4:] *= 100.0  # higher uncertainty for velocities

        # Measurement noise covariance
        self.R = np.eye(4) * 10.0

        # Initial state covariance
        self.P = np.eye(8) * 10.0
        self.P[4:, 4:] *= 100.0

        # Initial state
        cx, cy, w, h = _xyxy_to_cxcywh(bbox)
        self.x = np.array([cx, cy, w, h, 0, 0, 0, 0], dtype=float)

    def predict(self):
        """Predict next state."""
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.get_bbox()

    def update(self, bbox):
        """Correct state with observed measurement."""
        cx, cy, w, h = _xyxy_to_cxcywh(bbox)
        z = np.array([cx, cy, w, h], dtype=float)

        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ (z - self.H @ self.x)
        self.P = (np.eye(8) - K @ self.H) @ self.P

    def get_bbox(self):
        cx, cy, w, h = self.x[:4]
        return _cxcywh_to_xyxy(cx, cy, w, h)


def _xyxy_to_cxcywh(bbox):
    x, y, w, h = bbox[:4]
    return x + w / 2, y + h / 2, w, h


def _cxcywh_to_xyxy(cx, cy, w, h):
    return cx - w / 2, cy - h / 2, w, h


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------
class Track:
    _id_counter = 0

    def __init__(self, bbox, face_data):
        Track._id_counter += 1
        self.track_id = Track._id_counter
        self.kalman = KalmanBoxFilter(bbox)
        self.face_data = face_data   # original full face array from detector
        self.hits = 1
        self.age = 1
        self.time_since_update = 0
        self.state = "confirmed" if self.hits >= 1 else "tentative"

    def predict(self):
        self.kalman.predict()
        self.age += 1
        self.time_since_update += 1

    def update(self, bbox, face_data):
        self.kalman.update(bbox)
        self.face_data = face_data
        self.hits += 1
        self.time_since_update = 0
        if self.hits >= 3:
            self.state = "confirmed"

    def get_bbox(self):
        x, y, w, h = self.kalman.get_bbox()
        return np.array([max(0, x), max(0, y), max(1, w), max(1, h)])


# ---------------------------------------------------------------------------
# IoU helpers
# ---------------------------------------------------------------------------
def iou_batch(bboxes_a, bboxes_b):
    """
    Compute IoU matrix between two sets of [x,y,w,h] bboxes.
    Returns (len_a, len_b) matrix.
    """
    ax, ay, aw, ah = bboxes_a[:, 0], bboxes_a[:, 1], bboxes_a[:, 2], bboxes_a[:, 3]
    bx, by, bw, bh = bboxes_b[:, 0], bboxes_b[:, 1], bboxes_b[:, 2], bboxes_b[:, 3]

    # Convert to x1,y1,x2,y2
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1 = np.maximum(ax[:, None], bx[None, :])
    inter_y1 = np.maximum(ay[:, None], by[None, :])
    inter_x2 = np.minimum(ax2[:, None], bx2[None, :])
    inter_y2 = np.minimum(ay2[:, None], by2[None, :])

    inter_w = np.maximum(0, inter_x2 - inter_x1)
    inter_h = np.maximum(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = aw * ah
    area_b = bw * bh
    union_area = area_a[:, None] + area_b[None, :] - inter_area

    return inter_area / np.maximum(union_area, 1e-6)


# ---------------------------------------------------------------------------
# ByteTracker — main class
# ---------------------------------------------------------------------------
class ByteTracker:
    """
    ByteTrack algorithm: Kalman Filter prediction + IoU-based Hungarian matching.
    High-confidence detections are matched first, then low-confidence ones to
    recover lost tracks — reducing ID switches during occlusion.

    Interface matches CentroidTracker:
        tracker.update(faces)  →  [(track_id, face_array), ...]
    """

    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.3,
        max_time_lost: int = 30,
    ):
        self.track_thresh = track_thresh   # min detection score for high-conf
        self.match_thresh = match_thresh   # min IoU for a valid match
        self.max_time_lost = max_time_lost # frames before a track is deleted
        self.tracks: list[Track] = []

    def update(self, detections):
        """
        Args:
            detections: list/array of face rows [x, y, w, h, score, lmk_x1, ...]
                        (YuNet output). Score at index 4.
        Returns:
            List of (track_id, face_array) for visible confirmed tracks.
        """
        if len(detections) == 0:
            for t in self.tracks:
                t.predict()
            self.tracks = [t for t in self.tracks
                           if t.time_since_update <= self.max_time_lost]
            return self._get_outputs()

        dets = np.array(detections)
        scores = dets[:, 4] if dets.shape[1] > 4 else np.ones(len(dets))

        high_mask = scores >= self.track_thresh
        high_dets = dets[high_mask]
        low_dets  = dets[~high_mask]

        # Predict all existing tracks
        for t in self.tracks:
            t.predict()

        unmatched_tracks = list(range(len(self.tracks)))

        # --- Step 1: Match high-confidence detections to existing tracks ---
        if len(high_dets) > 0 and len(self.tracks) > 0:
            track_bboxes = np.array([t.get_bbox() for t in self.tracks])
            det_bboxes   = high_dets[:, :4]
            iou_matrix   = iou_batch(track_bboxes, det_bboxes)  # (T, D)
            cost_matrix  = 1 - iou_matrix

            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            matched_tracks = set()
            matched_dets   = set()

            for r, c in zip(row_ind, col_ind):
                if iou_matrix[r, c] >= self.match_thresh:
                    self.tracks[r].update(high_dets[c, :4], high_dets[c])
                    matched_tracks.add(r)
                    matched_dets.add(c)

            unmatched_tracks = [i for i in range(len(self.tracks))
                                if i not in matched_tracks]
            unmatched_high_dets = [i for i in range(len(high_dets))
                                   if i not in matched_dets]
        else:
            unmatched_high_dets = list(range(len(high_dets)))

        # --- Step 2: Match low-confidence detections to remaining tracks ---
        if len(low_dets) > 0 and len(unmatched_tracks) > 0:
            track_bboxes = np.array([self.tracks[i].get_bbox()
                                     for i in unmatched_tracks])
            det_bboxes   = low_dets[:, :4]
            iou_matrix   = iou_batch(track_bboxes, det_bboxes)
            cost_matrix  = 1 - iou_matrix

            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            still_unmatched = []

            for idx, r in enumerate(row_ind):
                c = col_ind[idx]
                if iou_matrix[r, c] >= self.match_thresh:
                    self.tracks[unmatched_tracks[r]].update(
                        low_dets[c, :4], low_dets[c])
                else:
                    still_unmatched.append(unmatched_tracks[r])

            unmatched_tracks = still_unmatched

        # --- Step 3: Initialise new tracks for unmatched high-conf detections ---
        for i in unmatched_high_dets:
            self.tracks.append(Track(high_dets[i, :4], high_dets[i]))

        # --- Step 4: Remove dead tracks ---
        self.tracks = [t for t in self.tracks
                       if t.time_since_update <= self.max_time_lost]

        return self._get_outputs()

    def _get_outputs(self):
        """Return (track_id, face_data) for confirmed, visible tracks."""
        result = []
        for t in self.tracks:
            if t.time_since_update == 0 and t.state == "confirmed":
                # Blend Kalman-smoothed bbox back into face_data
                smoothed = t.get_bbox()
                face = t.face_data.copy().astype(float)
                face[:4] = smoothed
                result.append((t.track_id, face))
        return result
