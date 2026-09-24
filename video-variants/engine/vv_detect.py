"""Find where faces/heads are across a whole clip, so on-screen text can avoid them.

Three detectors are combined because each misses cases the others catch:
  * YuNet (OpenCV)            - frontal and three-quarter faces, small faces
  * MediaPipe BlazeFace       - close-up selfie faces
  * MediaPipe Pose landmarker - head position from nose/eye/ear points, which
                                still works for side profiles and turned heads
Every detection from every sampled frame is kept (with generous margins for
hair and chin), because the text is static for the whole clip.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import cv2
import numpy as np

W, H = 1080, 1920
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    src: str = ""
    tier: str = "face"  # core = eyes/nose/mouth, face = whole face+hair, halo = extra margin (neck etc.)

    @property
    def core(self) -> bool:
        return self.tier == "core"

    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)

    def inter(self, x0, y0, x1, y1) -> float:
        ix = max(0.0, min(self.x1, x1) - max(self.x0, x0))
        iy = max(0.0, min(self.y1, y1) - max(self.y0, y0))
        return ix * iy

    def as_list(self):
        return [round(self.x0), round(self.y0), round(self.x1), round(self.y1)]


def normalize_frame(frame: np.ndarray, fast: bool = False) -> np.ndarray:
    """Scale to cover 1080x1920 and centre-crop: same geometry as the ffmpeg chain."""
    h, w = frame.shape[:2]
    s = max(W / w, H / h)
    nw, nh = max(W, round(w * s)), max(H, round(h * s))
    if (nw, nh) != (w, h):
        interp = cv2.INTER_LINEAR if fast else cv2.INTER_LANCZOS4
        frame = cv2.resize(frame, (nw, nh), interpolation=interp)
    x = (nw - W) // 2
    y = (nh - H) // 2
    return frame[y:y + H, x:x + W]


def sample_frames(path: str, every_s: float = 0.25, max_frames: int = 60):
    """Read the clip once, front to back, keeping one frame every `every_s` seconds."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps * every_s)))
    if n and n / step > max_frames:
        step = int(np.ceil(n / max_frames))
    frames, i = [], 0
    last = None
    while True:
        if not cap.grab():
            break
        if i % step == 0:
            ok, f = cap.retrieve()
            if ok:
                frames.append(normalize_frame(f, fast=True))
        last = i
        i += 1
    # make sure the final frame is represented
    if last is not None and last % step != 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, last)
        ok, f = cap.read()
        if ok:
            frames.append(normalize_frame(f, fast=True))
    cap.release()
    return frames


class HeadDetector:
    def close(self):
        for d in (self.blaze, self.pose):
            try:
                d.close()
            except Exception:
                pass

    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision

        self.mp = mp
        self.yunet = cv2.FaceDetectorYN.create(
            os.path.join(MODELS, "face_detection_yunet_2023mar.onnx"), "", (W // 2, H // 2), 0.6, 0.3, 50)
        self.blaze = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=mpt.BaseOptions(model_asset_path=os.path.join(MODELS, "blaze_face_short_range.tflite")),
            min_detection_confidence=0.55))
        self.pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=mpt.BaseOptions(model_asset_path=os.path.join(MODELS, "pose_landmarker_full.task")),
            running_mode=vision.RunningMode.IMAGE, num_poses=3,
            min_pose_detection_confidence=0.5, min_pose_presence_confidence=0.5))

    @staticmethod
    def _padded(x, y, w, h, src):
        """Face box -> keep-out boxes: halo (soft), face incl. hair (hard), core (hard)."""
        return [
            Box(x - 0.30 * w, y - 0.55 * h, x + 1.30 * w, y + 1.30 * h, src, "halo"),
            Box(x - 0.12 * w, y - 0.30 * h, x + 1.12 * w, y + 1.08 * h, src, "face"),
            Box(x + 0.05 * w, y + 0.10 * h, x + 0.95 * w, y + 0.95 * h, src, "core"),
        ]

    def detect(self, frame: np.ndarray) -> list[Box]:
        boxes: list[Box] = []
        small = cv2.resize(frame, (W // 2, H // 2), interpolation=cv2.INTER_AREA)

        # YuNet on the half-size frame.
        self.yunet.setInputSize((W // 2, H // 2))
        _, faces = self.yunet.detect(small)
        if faces is not None:
            for f in faces:
                x, y, w, h = (float(v) * 2 for v in f[:4])
                boxes += self._padded(x, y, w, h, "yunet")

        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))

        for d in self.blaze.detect(img).detections:
            b = d.bounding_box
            boxes += self._padded(b.origin_x * 2, b.origin_y * 2, b.width * 2, b.height * 2, "blaze")

        # Pose: head from the 11 face landmarks (0-10), scaled by shoulder width.
        for lms in self.pose.detect(img).pose_landmarks:
            pts = [(lm.x * W, lm.y * H) for lm in lms[:11] if (lm.visibility or 0) > 0.35]
            if len(pts) < 2:
                continue
            p = np.array(pts)
            span = float(max(np.ptp(p[:, 0]), np.ptp(p[:, 1])))
            sh = 0.0
            ls, rs = lms[11], lms[12]
            if (ls.visibility or 0) > 0.35 and (rs.visibility or 0) > 0.35:
                sh = float(np.hypot((ls.x - rs.x) * W, (ls.y - rs.y) * H))
            size = max(span * 2.4, sh * 0.45, 0.06 * W)
            cx, cy = float(p[:, 0].mean()), float(p[:, 1].mean())
            boxes.append(Box(cx - 0.64 * size, cy - 0.92 * size, cx + 0.64 * size, cy + 0.72 * size, "pose", "halo"))
            boxes.append(Box(cx - 0.50 * size, cy - 0.78 * size, cx + 0.50 * size, cy + 0.55 * size, "pose", "face"))
            boxes.append(Box(cx - 0.30 * size, cy - 0.28 * size, cx + 0.30 * size, cy + 0.40 * size, "pose", "core"))

        for b in boxes:  # clamp to frame
            b.x0, b.y0 = max(0.0, b.x0), max(0.0, b.y0)
            b.x1, b.y1 = min(float(W), b.x1), min(float(H), b.y1)
        return [b for b in boxes if b.area() > 0]


def _iou(a: Box, b: Box) -> float:
    i = a.inter(b.x0, b.y0, b.x1, b.y1)
    u = a.area() + b.area() - i
    return i / u if u > 0 else 0.0


def analyze(path: str, detector: HeadDetector | None = None) -> dict:
    """Keep-out boxes for the clip, plus sampled frames for colour analysis.

    A detection only counts if something overlaps it in several other sampled
    frames: real faces persist, one-frame false positives (a chest, a vase,
    a pattern) do not. Tiny faces (far-away passers-by) become 'minor' boxes,
    which placement avoids when it can but does not treat as absolute.
    """
    det = detector or HeadDetector()
    frames = sample_frames(path)
    per_frame: list[list[Box]] = [det.detect(f) for f in frames]
    n = len(frames)
    need = max(2, int(round(0.12 * n)))
    keep: list[Box] = []
    minor: list[Box] = []
    for fi, fb in enumerate(per_frame):
        for b in fb:
            support = sum(
                1 for fj, other in enumerate(per_frame)
                if fj != fi and any(o.tier == b.tier and _iou(o, b) > 0.25 for o in other)
            )
            if support + 1 < need:
                continue
            face_h = (b.y1 - b.y0) / {"halo": 1.85, "face": 1.38, "core": 0.85}[b.tier]
            (keep if face_h >= 0.03 * H or b.src == "pose" else minor).append(b)
    return {
        "frames": frames,
        "boxes": keep,
        "minor_boxes": minor,
        "frames_with_faces": sum(1 for fb in per_frame if fb),
        "frames_sampled": n,
        "dropped": sum(len(fb) for fb in per_frame) - len(keep) - len(minor),
    }
