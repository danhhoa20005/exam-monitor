"""
Team-trained head-turn classifier (turn / normal) run on per-student crops.

Trained with training/train_turn_cls.py on SCB BowTurnHead + DS-03 crops. It gives a second,
appearance-based opinion next to the keypoint geometry rules in pose_behavior.py.
"""
from typing import List, Optional, Sequence

try:
    import numpy as np
except ImportError:
    np = None


def crop_person(img, box):
    """
    Upper body (head + shoulders + hands on desk) of one person, padded 10% each side.
    MUST stay identical to crop_person() in training/prepare_turn_cls.py, or the model
    sees differently framed crops than it was trained on.
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    y2 = y1 + bh * 0.65
    x1, x2 = x1 - 0.1 * bw, x2 + 0.1 * bw
    y1 = y1 - 0.1 * bh
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 16 or y2 - y1 < 16:
        return None
    return img[y1:y2, x1:x2]


class TurnClassifier:
    def __init__(self, weights_path: str, imgsz: int = 224):
        from ultralytics import YOLO
        self.model = YOLO(weights_path)
        self.imgsz = imgsz
        self.turn_idx = next(k for k, v in self.model.names.items() if v == "turn")

    def predict(self, frame_bgr, boxes_xyxy_px: Sequence[Sequence[float]]) -> List[Optional[float]]:
        """P(turn) per box, None where the crop is too small to judge."""
        crops, idx = [], []
        for i, box in enumerate(boxes_xyxy_px):
            c = crop_person(frame_bgr, box)
            if c is not None:
                crops.append(c)
                idx.append(i)
        probs: List[Optional[float]] = [None] * len(boxes_xyxy_px)
        if crops:
            for i, r in zip(idx, self.model(crops, imgsz=self.imgsz, verbose=False)):
                probs[i] = float(r.probs.data[self.turn_idx])
        return probs
