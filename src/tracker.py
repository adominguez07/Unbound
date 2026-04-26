import time
from dataclasses import dataclass, field

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .resource_paths import resource_path

# Landmark index 1 is the nose tip in MediaPipe's 478-point face mesh.
NOSE_TIP_INDEX = 1


@dataclass
class FrameResult:
    nose_tip: tuple[float, float]          # normalized (x, y) in [0, 1]
    blendshapes: dict[str, float]
    frame: np.ndarray                      # raw BGR frame for optional preview


class FaceTracker:
    def __init__(self, model_path: str | None = None, camera_index: int = 0) -> None:
        if model_path is None:
            model_path = str(resource_path("models/face_landmarker.task"))

        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

        self._last_timestamp_ms: int = 0

        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open camera index {camera_index}. "
                "Check that a webcam is connected and not in use by another application."
            )

    def process_frame(self) -> FrameResult | None:
        ok, frame_bgr = self._cap.read()
        if not ok:
            return None

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        # detect_for_video requires strictly increasing timestamps in milliseconds.
        # Two frames captured within the same millisecond would produce equal values,
        # so clamp to at least one tick ahead of the previous call.
        timestamp_ms = max(
            time.monotonic_ns() // 1_000_000,
            self._last_timestamp_ms + 1,
        )
        self._last_timestamp_ms = timestamp_ms

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]
        nose = landmarks[NOSE_TIP_INDEX]
        nose_tip = (nose.x, nose.y)

        blendshapes: dict[str, float] = {}
        if result.face_blendshapes:
            for bs in result.face_blendshapes[0]:
                blendshapes[bs.category_name] = bs.score

        return FrameResult(nose_tip=nose_tip, blendshapes=blendshapes, frame=frame_bgr)

    def release(self) -> None:
        self._cap.release()
        self._landmarker.close()
