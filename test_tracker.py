"""
Full pipeline smoke-test: face tracking + cursor control + gesture detection + actions.
Run from the repo root with the venv active:

    python test_tracker.py [camera_index]

Startup: hold your head still for ~2 seconds while the neutral position is captured.
Then move your nose to move the cursor. Gestures print to the console and fire mouse actions.

To change what each gesture does, edit GESTURE_BINDINGS in src/action_dispatcher.py.
To change sensitivity / thresholds, edit the CONST blocks at the top of each src/ file.

Press Q in the preview window to quit.
"""

import sys
import cv2
from src.tracker import FaceTracker
from src.cursor_controller import CursorController
from src.gesture_detector import GestureDetector
from src.action_dispatcher import ActionDispatcher

# Frames to average for the neutral calibration at startup (~2 s at 30 fps)
CALIBRATION_FRAMES = 60

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

    cursor = CursorController()

    dispatcher = ActionDispatcher(
        on_pause_toggle=lambda: _toggle_pause(cursor),
    )
    detector = GestureDetector(
        on_tap=dispatcher.on_tap,
        on_hold_start=dispatcher.on_hold_start,
        on_hold_end=dispatcher.on_hold_end,
    )

    # --- Calibration phase ---
    print(f"Hold still — calibrating neutral position ({CALIBRATION_FRAMES} frames)...")
    neutral_samples: list[tuple[float, float]] = []

    while len(neutral_samples) < CALIBRATION_FRAMES:
        result = tracker.process_frame()
        if result is None:
            continue
        neutral_samples.append(result.nose_tip)

        remaining = CALIBRATION_FRAMES - len(neutral_samples)
        cv2.imshow("NoseCursor — calibrating (hold still)", result.frame)
        cv2.setWindowTitle(
            "NoseCursor — calibrating (hold still)",
            f"Calibrating... {remaining} frames left",
        )
        if cv2.waitKey(1) & 0xFF == ord("q"):
            tracker.release()
            cv2.destroyAllWindows()
            return

    avg_x = sum(s[0] for s in neutral_samples) / len(neutral_samples)
    avg_y = sum(s[1] for s in neutral_samples) / len(neutral_samples)
    cursor.set_neutral((avg_x, avg_y))
    print(f"Neutral set to ({avg_x:.4f}, {avg_y:.4f}). Tracking active.")
    cv2.destroyAllWindows()

    # --- Main loop ---
    try:
        while True:
            result = tracker.process_frame()
            if result is None:
                continue

            cursor.update(result.nose_tip)
            detector.update(result.blendshapes)

            # Console blendshape readout (only non-trivial values)
            nx, ny = result.nose_tip
            parts = [f"nose=({nx:.3f},{ny:.3f})"]
            for name in WATCHED_BLENDSHAPES:
                score = result.blendshapes.get(name, 0.0)
                if score > 0.05:
                    parts.append(f"{name}={score:.2f}")
            print("  ".join(parts))

            # Preview window
            preview = result.frame.copy()
            h, w = preview.shape[:2]
            cx, cy = int(nx * w), int(ny * h)
            cv2.circle(preview, (cx, cy), 6, (0, 255, 0), -1)
            status = "PAUSED" if cursor.paused else "tracking"
            cv2.putText(
                preview, status, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (0, 0, 255) if cursor.paused else (0, 255, 0), 2,
            )
            cv2.imshow("NoseCursor (Q to quit)", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        tracker.release()
        cv2.destroyAllWindows()


def _toggle_pause(cursor: CursorController) -> None:
    cursor.paused = not cursor.paused
    print(f"Tracking {'PAUSED' if cursor.paused else 'RESUMED'}")


if __name__ == "__main__":
    main()
