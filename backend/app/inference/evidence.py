"""
FT-06 evidence clips.

Keeps the last PRE seconds of frames (as the JPEG bytes the client sent). When a student turns
REVIEW, the clip = those PRE seconds + the next POST seconds, written as an H.264 MP4 (plays in
every browser) with the flagged student boxed in red. Encoding runs on a background thread so it
never delays inference.
"""
import os
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

Box = Tuple[float, float, float, float]   # normalised x1, y1, x2, y2


@dataclass
class _Frame:
    t_ms: int
    jpeg: bytes
    boxes: Dict[int, Box]


@dataclass
class _Clip:
    clip_id: str
    track_id: int
    reasons: List[str]
    trigger_ms: int
    frames: List[_Frame]


class EvidenceRecorder:
    def __init__(self, out_dir, pre_s: float = 5.0, post_s: float = 5.0, max_clips: int = 50,
                 async_write: bool = True):
        self.out_dir = Path(out_dir)
        self.pre_ms = int(pre_s * 1000)
        self.post_ms = int(post_s * 1000)
        self.max_clips = max_clips          # caps disk use when alerts fire repeatedly
        self.async_write = async_write
        self._buffer: deque = deque()
        self._pending: Dict[str, _Clip] = {}
        self._event_clip: Dict[str, str] = {}
        self._ready: set = set()
        self._lock = threading.Lock()
        self._n_clips = 0

    def add_frame(self, t_ms: int, jpeg: bytes, boxes: Dict[int, Box]):
        frame = _Frame(t_ms, jpeg, dict(boxes))
        self._buffer.append(frame)
        while self._buffer and t_ms - self._buffer[0].t_ms > self.pre_ms:
            self._buffer.popleft()
        done = []
        for clip_id, clip in self._pending.items():
            clip.frames.append(frame)
            if t_ms - clip.trigger_ms >= self.post_ms:
                done.append(clip_id)
        for clip_id in done:
            self._finish(clip_id)

    def trigger(self, event_id: str, track_id: int, reason: str, t_ms: int) -> bool:
        """Start a clip for a new event. Returns False when the per-session clip limit is reached."""
        for clip_id, clip in self._pending.items():
            # TURNING + PHONE raised on the same frame for one student: one clip is enough
            if clip.track_id == track_id and clip.trigger_ms == t_ms:
                clip.reasons.append(reason)
                self._event_clip[event_id] = clip_id
                return True
        if self._n_clips >= self.max_clips:
            return False
        self._n_clips += 1
        self._pending[event_id] = _Clip(event_id, track_id, [reason], t_ms, list(self._buffer))
        self._event_clip[event_id] = event_id
        return True

    def flush(self):
        """Write every unfinished clip now (video source changed or session stopped)."""
        for clip_id in list(self._pending):
            self._finish(clip_id)

    def reset_buffer(self):
        """Drop buffered history (new video source): it must not appear before the next alert."""
        self._buffer.clear()

    def status(self, event_id: str) -> str:
        clip_id = self._event_clip.get(event_id)
        if clip_id is None:
            return "missing"
        with self._lock:
            return "ready" if clip_id in self._ready else "recording"

    def path_for(self, event_id: str) -> Optional[Path]:
        if self.status(event_id) != "ready":
            return None
        return self.out_dir / f"{self._event_clip[event_id]}.mp4"

    def _finish(self, clip_id: str):
        clip = self._pending.pop(clip_id)
        if self.async_write:
            threading.Thread(target=self._write, args=(clip,), daemon=True).start()
        else:
            self._write(clip)

    def _write(self, clip: _Clip):
        frames = [(f, cv2.imdecode(np.frombuffer(f.jpeg, np.uint8), cv2.IMREAD_COLOR)) for f in clip.frames]
        frames = [(f, img) for f, img in frames if img is not None]
        if not frames:
            return
        h, w = frames[0][1].shape[:2]
        span_s = (frames[-1][0].t_ms - frames[0][0].t_ms) / 1000.0
        fps = min(30.0, max(2.0, (len(frames) - 1) / span_s)) if span_s > 0 else 10.0

        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{clip.clip_id}.mp4"
        tmp = self.out_dir / f"{clip.clip_id}.part.mp4"
        writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"avc1"), fps, (w, h))
        if not writer.isOpened():   # no H.264 encoder on this machine: still save, download-only
            writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

        label = f"#{clip.track_id} {', '.join(clip.reasons)}"
        for f, img in frames:
            if img.shape[:2] != (h, w):
                img = cv2.resize(img, (w, h))
            box = f.boxes.get(clip.track_id)
            if box is not None:
                x1, y1, x2, y2 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(img, label, (x1, max(14, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            cv2.putText(img, f"{(f.t_ms - clip.trigger_ms) / 1000:+.1f}s", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            writer.write(img)
        writer.release()
        os.replace(tmp, path)
        with self._lock:
            self._ready.add(clip.clip_id)
