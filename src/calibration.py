import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracker import FaceTracker
    from .settings_manager import SettingsManager

# Fraction of the peak blendshape score used as the trigger threshold.
# e.g. if the user's max wink score is 0.8, trigger = 0.8 * 0.65 = 0.52
TRIGGER_FRACTION = 0.65
# Release threshold is set lower than trigger to create hysteresis.
RELEASE_FRACTION = 0.35

# Blendshape key(s) that drive each named gesture
_GESTURE_BLENDSHAPES: dict[str, list[str]] = {
    "wink_left":     ["eyeBlinkLeft"],
    "wink_right":    ["eyeBlinkRight"],
    "mouth_open":    ["jawOpen"],
    "smile":         ["mouthSmileLeft", "mouthSmileRight"],
    "pucker":        ["mouthPucker"],
    "eyebrow_raise": ["browInnerUp"],
    "cheek_puff":    ["cheekPuff"],
}


class Calibrator:
    """
    Captures per-user baseline data and writes calibrated thresholds to SettingsManager.

    Usage (also exposed through the FastAPI endpoints later):
        calibrator = Calibrator(tracker, settings)
        calibrator.capture_neutral(duration_seconds=3)
        calibrator.capture_gesture("wink_left", duration_seconds=2)
    """

    def __init__(self, tracker: "FaceTracker", settings: "SettingsManager") -> None:
        self._tracker = tracker
        self._settings = settings

    # ------------------------------------------------------------------
    # Public calibration routines
    # ------------------------------------------------------------------

    def capture_neutral(self, duration_seconds: float = 3.0) -> dict[str, float]:
        """
        Record the user's resting face for N seconds.
        Averages nose position and all blendshape scores → stored as the personal baseline.
        Returns the averaged blendshape dict so the caller can display it.
        """
        print(f"Neutral calibration: hold still for {duration_seconds:.0f} seconds...")
        samples: list[dict] = []
        nose_xs: list[float] = []
        nose_ys: list[float] = []

        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            result = self._tracker.process_frame()
            if result is None:
                continue
            samples.append(result.blendshapes)
            nose_xs.append(result.nose_tip[0])
            nose_ys.append(result.nose_tip[1])

        if not samples:
            raise RuntimeError("No frames captured during neutral calibration.")

        avg_bs: dict[str, float] = {}
        all_keys = {k for s in samples for k in s}
        for key in all_keys:
            avg_bs[key] = sum(s.get(key, 0.0) for s in samples) / len(samples)

        neutral_x = sum(nose_xs) / len(nose_xs)
        neutral_y = sum(nose_ys) / len(nose_ys)

        self._settings.set("neutral_nose_x", neutral_x)
        self._settings.set("neutral_nose_y", neutral_y)
        self._settings.set("neutral_blendshapes", avg_bs)
        self._settings.save()

        print(f"Neutral set: nose=({neutral_x:.4f}, {neutral_y:.4f}), {len(samples)} frames.")
        return avg_bs

    def capture_gesture(
        self,
        gesture_name: str,
        duration_seconds: float = 2.0,
    ) -> dict[str, float]:
        """
        Ask the user to perform a gesture for N seconds.
        Records the peak blendshape score and writes calibrated trigger/release
        thresholds into settings at TRIGGER_FRACTION / RELEASE_FRACTION of that peak.
        Returns the new threshold dict {"trigger": ..., "release": ...}.
        """
        if gesture_name not in _GESTURE_BLENDSHAPES:
            raise ValueError(f"Unknown gesture: {gesture_name!r}")

        keys = _GESTURE_BLENDSHAPES[gesture_name]
        print(f"Gesture calibration [{gesture_name}]: perform the gesture for {duration_seconds:.0f} s...")

        peak: float = 0.0
        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            result = self._tracker.process_frame()
            if result is None:
                continue
            score = sum(result.blendshapes.get(k, 0.0) for k in keys) / len(keys)
            if score > peak:
                peak = score

        if peak < 0.05:
            raise RuntimeError(
                f"No signal detected for '{gesture_name}'. "
                "Make sure to perform the gesture clearly during calibration."
            )

        trigger = round(min(peak * TRIGGER_FRACTION, 0.99), 3)
        release = round(min(peak * RELEASE_FRACTION, trigger - 0.05), 3)
        release = max(release, 0.05)

        thresholds = self._settings.get("gesture_thresholds") or {}
        thresholds[gesture_name] = {"trigger": trigger, "release": release}
        self._settings.set("gesture_thresholds", thresholds)
        self._settings.save()

        print(f"  peak={peak:.3f}  trigger={trigger:.3f}  release={release:.3f}")
        return {"trigger": trigger, "release": release}

    def capture_all_gestures(self, duration_seconds: float = 2.0) -> None:
        """Walk through every gesture in sequence, calibrating each one."""
        self.capture_neutral(duration_seconds=3.0)
        for gesture in _GESTURE_BLENDSHAPES:
            input(f"\nPress Enter when ready to calibrate '{gesture}'...")
            try:
                self.capture_gesture(gesture, duration_seconds=duration_seconds)
            except RuntimeError as exc:
                print(f"  Skipped: {exc}")
        print("\nCalibration complete. Settings saved.")
