import json
import threading
from pathlib import Path
from typing import Any, Callable

from .resource_paths import resource_path

# Where user settings persist between runs
_USER_SETTINGS_PATH = Path.home() / ".unbound" / "settings.json"

# Keys that must be floats in [0.0, 1.0]
_UNIT_FLOAT_KEYS = {
    "smoothing_alpha",
    "deadzone_radius",
}

# Keys that must be positive floats
_POSITIVE_FLOAT_KEYS = {"sensitivity", "acceleration_expo"}

# Valid values for enum-style keys
_ENUM_KEYS: dict[str, set] = {
    "movement_mode": {"absolute", "joystick"},
}

_VALID_ACTIONS = {
    "left_click", "right_click", "double_click",
    "scroll_up", "scroll_down", "drag_toggle",
    "pause_tracking", "open_osk", "dictation_toggle", "none",
}

_VALID_GESTURES = {
    "wink_left", "wink_right", "mouth_open",
    "smile", "pucker", "eyebrow_raise",
}


class SettingsManager:
    """
    Loads, validates, persists, and hot-reloads application settings.

    Settings are written to ~/.unbound/settings.json.  On first run the
    bundled config/default_settings.json is copied there automatically.

    Register a callback with on_change() to be notified when any value changes
    so live components (tracker, cursor controller) can hot-reload without restart.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._listeners: list[Callable[[str, Any], None]] = []
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        value = self._validate(key, value)
        with self._lock:
            self._data[key] = value
        self._notify(key, value)

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def update(self, patch: dict[str, Any]) -> None:
        """Apply multiple keys at once, validating each independently.

        Invalid keys are skipped with a console warning so that a bad threshold
        slider value never silently blocks a gesture binding change.
        """
        applied = {}
        for k, v in patch.items():
            try:
                applied[k] = self._validate(k, v)
            except (ValueError, TypeError) as exc:
                print(f"[settings] skipped invalid value for {k!r}: {exc}")
        with self._lock:
            self._data.update(applied)
        for k, v in applied.items():
            self._notify(k, v)

    def on_change(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback(key, new_value) fired whenever a setting changes."""
        self._listeners.append(callback)

    def save(self) -> None:
        _USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = dict(self._data)
        _USER_SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        defaults = self._load_defaults()
        if _USER_SETTINGS_PATH.exists():
            try:
                user = json.loads(_USER_SETTINGS_PATH.read_text(encoding="utf-8"))
                # Merge: user values override defaults, but defaults fill missing keys
                merged = {**defaults, **user}
                # Nested dicts need a deeper merge
                for nested_key in ("gesture_bindings", "gesture_thresholds"):
                    if nested_key in defaults:
                        merged[nested_key] = {**defaults[nested_key], **user.get(nested_key, {})}
                with self._lock:
                    self._data = merged
                return
            except (json.JSONDecodeError, OSError):
                pass  # fall through to defaults
        with self._lock:
            self._data = defaults
        self.save()  # write defaults to user path on first run

    def reset_to_defaults(self) -> None:
        with self._lock:
            self._data = self._load_defaults()
        self.save()
        for k, v in self._data.items():
            self._notify(k, v)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_defaults(self) -> dict[str, Any]:
        path = resource_path("config/default_settings.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def _validate(self, key: str, value: Any) -> Any:
        if key in _UNIT_FLOAT_KEYS:
            value = float(value)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{key} must be between 0.0 and 1.0, got {value}")

        elif key in _POSITIVE_FLOAT_KEYS:
            value = float(value)
            if value <= 0:
                raise ValueError(f"{key} must be positive, got {value}")

        elif key in _ENUM_KEYS:
            if value not in _ENUM_KEYS[key]:
                raise ValueError(f"{key} must be one of {_ENUM_KEYS[key]}, got {value!r}")

        elif key == "camera_index":
            value = int(value)
            if value < 0:
                raise ValueError(f"camera_index must be >= 0, got {value}")

        elif key == "hold_duration_ms":
            value = int(value)
            if value < 0:
                raise ValueError(f"hold_duration_ms must be >= 0, got {value}")

        elif key == "failsafe_enabled":
            value = bool(value)

        elif key == "gesture_bindings":
            if not isinstance(value, dict):
                raise ValueError("gesture_bindings must be a dict")
            for gesture, action in value.items():
                if gesture not in _VALID_GESTURES:
                    raise ValueError(f"Unknown gesture: {gesture!r}")
                if action not in _VALID_ACTIONS:
                    raise ValueError(f"Unknown action: {action!r}")

        elif key == "gesture_thresholds":
            if not isinstance(value, dict):
                raise ValueError("gesture_thresholds must be a dict")
            for gesture, thresholds in value.items():
                if gesture not in _VALID_GESTURES:
                    raise ValueError(f"Unknown gesture: {gesture!r}")
                t = float(thresholds.get("trigger", 0))
                r = float(thresholds.get("release", 0))
                if not (0.0 <= t <= 1.0 and 0.0 <= r <= 1.0):
                    raise ValueError(f"Thresholds for {gesture} must be in [0, 1]")
                if r >= t:
                    raise ValueError(
                        f"release threshold ({r}) must be below trigger ({t}) for {gesture}"
                    )

        return value

    def _notify(self, key: str, value: Any) -> None:
        for cb in self._listeners:
            try:
                cb(key, value)
            except Exception:
                pass
