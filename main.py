"""
NoseCursor entry point.

Usage:
    python main.py [--camera INDEX] [--browser]

--browser  Open the settings UI in the system browser instead of a native window.
           Use this while iterating on the UI without needing PyWebView installed.
"""

import argparse
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from src.settings_manager import SettingsManager
from src.tracker import FaceTracker
from src.cursor_controller import CursorController
from src.gesture_detector import GestureDetector
from src.action_dispatcher import ActionDispatcher
from src.calibration import Calibrator
from src.server import AppState, create_app


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_uvicorn(app, host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _tracker_loop(
    state: AppState,
    cursor: CursorController,
    detector: GestureDetector,
) -> None:
    neutral_samples: list[tuple[float, float]] = []
    print("Hold still — capturing neutral position (2 s)...")

    while len(neutral_samples) < 60:
        if state.shutdown_requested:
            return
        result = state.tracker.process_frame()
        if result is None:
            continue
        neutral_samples.append(result.nose_tip)
        state.update_blendshapes(result.blendshapes)

    avg_x = sum(s[0] for s in neutral_samples) / len(neutral_samples)
    avg_y = sum(s[1] for s in neutral_samples) / len(neutral_samples)
    cursor.set_neutral((avg_x, avg_y))
    print(f"Neutral set ({avg_x:.4f}, {avg_y:.4f}). Tracking active.")

    while not state.shutdown_requested:
        # Yield to calibration: the calibrator calls process_frame() directly,
        # so we stop calling it here to avoid concurrent camera access.
        if state.calibration_in_progress:
            time.sleep(0.01)
            continue

        result = state.tracker.process_frame()
        if result is None:
            continue

        state.update_blendshapes(result.blendshapes)
        cursor.update(result.nose_tip)
        detector.update(result.blendshapes)


def _wire_hot_reload(
    settings: SettingsManager,
    cursor: CursorController,
    detector: GestureDetector,
    dispatcher: ActionDispatcher,
) -> None:
    """Apply settings changes live without restarting the app."""
    import pyautogui

    def on_change(key: str, value) -> None:
        if key == "sensitivity":
            cursor.sensitivity = float(value)
        elif key == "smoothing_alpha":
            cursor.smoothing_alpha = float(value)
        elif key == "deadzone_radius":
            cursor.deadzone_radius = float(value)
        elif key == "acceleration_expo":
            cursor.acceleration_expo = float(value)
        elif key == "failsafe_enabled":
            pyautogui.FAILSAFE = bool(value)
        elif key == "gesture_bindings":
            dispatcher._bindings = dict(value)
        elif key == "gesture_thresholds":
            for name, thresholds in value.items():
                if name in detector._CONFIGS:
                    detector._CONFIGS[name].trigger = thresholds["trigger"]
                    detector._CONFIGS[name].release = thresholds["release"]

    settings.on_change(on_change)


def _toggle_pause(state: AppState, cursor: CursorController) -> None:
    cursor.paused = not cursor.paused
    state.is_paused = cursor.paused
    print(f"Tracking {'PAUSED' if cursor.paused else 'RESUMED'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NoseCursor")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open UI in system browser instead of native window",
    )
    args = parser.parse_args()

    settings = SettingsManager()
    camera_index = args.camera if args.camera is not None else settings.get("camera_index", 0)

    try:
        tracker = FaceTracker(camera_index=camera_index)
    except RuntimeError as exc:
        print(f"Camera error: {exc}", file=sys.stderr)
        sys.exit(1)

    cursor = CursorController(
        sensitivity=settings.get("sensitivity", 0.05),
        smoothing_alpha=settings.get("smoothing_alpha", 0.35),
        deadzone_radius=settings.get("deadzone_radius", 0.03),
        acceleration_expo=settings.get("acceleration_expo", 0.8),
        failsafe_enabled=settings.get("failsafe_enabled", True),
    )

    state = AppState(settings)
    state.tracker = tracker
    state.cursor = cursor
    state.calibrator = Calibrator(tracker, settings)

    dispatcher = ActionDispatcher(
        bindings=settings.get("gesture_bindings"),
        on_pause_toggle=lambda: _toggle_pause(state, cursor),
    )
    detector = GestureDetector(
        on_tap=dispatcher.on_tap,
        on_hold_start=dispatcher.on_hold_start,
        on_hold_end=dispatcher.on_hold_end,
        hold_duration_ms=settings.get("hold_duration_ms", 750),
    )

    _wire_hot_reload(settings, cursor, detector, dispatcher)

    app = create_app(state)
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    server_thread = threading.Thread(
        target=_run_uvicorn,
        args=(app, "127.0.0.1", port),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.4)  # wait for uvicorn to bind

    tracker_thread = threading.Thread(
        target=_tracker_loop,
        args=(state, cursor, detector),
        daemon=True,
    )
    tracker_thread.start()

    print(f"\nSettings UI: {url}\n")

    if args.browser:
        webbrowser.open(url)
        try:
            while not state.shutdown_requested:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nInterrupted.")
    else:
        from src.desktop_window import launch
        launch(url, state)

    state.shutdown_requested = True
    tracker.release()
    print("Goodbye.")


if __name__ == "__main__":
    main()
