import numpy as np
from collections import OrderedDict

class CentroidTracker:
    def __init__(self, max_disappeared=30, max_distance=150):
        self.next_object_id = 0
        # Stores tracked objects as {object_id: (centroid, bbox)}
        self.objects = OrderedDict()
        self.disappeared = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid, bbox):
        self.objects[self.next_object_id] = (centroid, bbox)
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]

    def update(self, rects):
        # rects is a list/array of [x, y, w, h] or longer arrays where first 4 are bounding box
        if len(rects) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return []

        input_centroids = np.zeros((len(rects), 2), dtype="int")
        for (i, face) in enumerate(rects):
            x, y, w, h = face[:4]
            c_x = int(x + w / 2.0)
            c_y = int(y + h / 2.0)
            input_centroids[i] = (c_x, c_y)

        if len(self.objects) == 0:
            for i in range(0, len(input_centroids)):
                self.register(input_centroids[i], rects[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = [obj[0] for obj in self.objects.values()]

            # Compute distance matrix
            D = np.linalg.norm(np.array(object_centroids)[:, np.newaxis] - input_centroids, axis=2)

            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                
                if D[row, col] > self.max_distance:
                    continue

                object_id = object_ids[row]
                self.objects[object_id] = (input_centroids[col], rects[col])
                self.disappeared[object_id] = 0

                used_rows.add(row)
                used_cols.add(col)

            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)

            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            for col in unused_cols:
                self.register(input_centroids[col], rects[col])

        # Return a list of tuples (object_id, bbox) for currently active objects that were updated this frame
        # We only return objects that are visible this frame (disappeared == 0)
        tracked_objects = []
        for object_id, data in self.objects.items():
            if self.disappeared[object_id] == 0:
                tracked_objects.append((object_id, data[1]))
                
        return tracked_objects
