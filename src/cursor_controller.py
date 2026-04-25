import pyautogui

# --- Tuning constants ---
SENSITIVITY     = 0.05    # pixels moved per unit of normalized nose displacement per frame
SMOOTHING_ALPHA = 0.35   # EMA weight for incoming sample; lower = smoother but laggier
DEADZONE_RADIUS = 0.05  # normalized nose offset below which movement is ignored
# ------------------------

# Disable the PyAutoGUI corner-failsafe only if the user explicitly turns it off.
# Default: leave it enabled so an accidental corner stop is possible.
pyautogui.PAUSE = 0  # remove the default 0.1 s delay between pyautogui calls


class CursorController:
    def __init__(
        self,
        sensitivity: float = SENSITIVITY,
        smoothing_alpha: float = SMOOTHING_ALPHA,
        deadzone_radius: float = DEADZONE_RADIUS,
        failsafe_enabled: bool = True,
    ) -> None:
        self.sensitivity = sensitivity
        self.smoothing_alpha = smoothing_alpha
        self.deadzone_radius = deadzone_radius
        self.paused = False

        pyautogui.FAILSAFE = failsafe_enabled

        self._neutral: tuple[float, float] | None = None
        self._smoothed_dx: float = 0.0
        self._smoothed_dy: float = 0.0

        self._screen_w, self._screen_h = pyautogui.size()

    def set_neutral(self, nose_tip: tuple[float, float]) -> None:
        """Record the resting nose position as the joystick origin."""
        self._neutral = nose_tip
        self._smoothed_dx = 0.0
        self._smoothed_dy = 0.0

    def update(self, nose_tip: tuple[float, float]) -> None:
        if self.paused or self._neutral is None:
            return

        nx, ny = nose_tip
        bx, by = self._neutral

        raw_dx = -(nx - bx)  # invert X so head-left moves cursor left
        raw_dy = ny - by

        # Deadzone — ignore sub-threshold tremor
        if abs(raw_dx) < self.deadzone_radius:
            raw_dx = 0.0
        if abs(raw_dy) < self.deadzone_radius:
            raw_dy = 0.0

        # Exponential moving average smoothing
        a = self.smoothing_alpha
        self._smoothed_dx = a * raw_dx + (1 - a) * self._smoothed_dx
        self._smoothed_dy = a * raw_dy + (1 - a) * self._smoothed_dy

        px = self._smoothed_dx * self.sensitivity * self._screen_w
        py = self._smoothed_dy * self.sensitivity * self._screen_h

        if px != 0.0 or py != 0.0:
            pyautogui.moveRel(px, py, _pause=False)
