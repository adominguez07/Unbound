"""
Standalone smoke-test for tracker.py.
Run from the repo root:
    python test_tracker.py

Press Q in the preview window (or the terminal) to quit.
Prints nose coordinates and a few blendshape scores each frame.
"""

import sys
import cv2
from src.tracker import FaceTracker

WATCHED_BLENDSHAPES = [
    "eyeBlinkLeft",
    "eyeBlinkRight",
    "jawOpen",
    "mouthSmileLeft",
    "browInnerUp",
    "cheekPuff",
    "mouthPucker",
]


def main() -> None:
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    try:
        tracker = FaceTracker(camera_index=camera_index)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print("Tracker running — press Q to quit.")

    try:
        while True:
            result = tracker.process_frame()
            if result is None:
                continue

            nx, ny = result.nose_tip
            print(f"nose=({nx:.3f}, {ny:.3f})", end="  ")
            for name in WATCHED_BLENDSHAPES:
                score = result.blendshapes.get(name, 0.0)
                if score > 0.01:
                    print(f"{name}={score:.2f}", end=" ")
            print()

            # Show a live preview with the nose position marked.
            preview = result.frame.copy()
            h, w = preview.shape[:2]
            cx, cy = int(nx * w), int(ny * h)
            cv2.circle(preview, (cx, cy), 6, (0, 255, 0), -1)
            cv2.imshow("NoseCursor — tracker test (Q to quit)", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        tracker.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
