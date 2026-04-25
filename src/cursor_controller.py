import pyautogui

# --- Tuning constants ---
SENSITIVITY       = 0.05   # peak speed multiplier at maximum nose displacement
SMOOTHING_ALPHA   = 0.35   # EMA weight for incoming sample; lower = smoother but laggier
DEADZONE_RADIUS   = 0.03   # normalized nose offset below which movement is ignored
ACCELERATION_EXPO = 0.8    # power curve exponent applied after the deadzone
                            # 1.0 = linear (same speed everywhere)
                            # 2.0 = quadratic (slow near center, fast at edges)
                            # try 1.5–2.5; higher = more aggressive acceleration
# ------------------------

pyautogui.PAUSE = 0  # remove the default 0.1 s delay between pyautogui calls


def _apply_curve(raw: float, deadzone: float, exponent: float) -> float:
    """Strip the deadzone then apply a power curve, preserving sign."""
    magnitude = abs(raw)
    if magnitude < deadzone:
        return 0.0
    # Remap so response starts at 0 just outside the deadzone and reaches 1.0 at max range.
    usable = 1.0 - deadzone
    normalized = (magnitude - deadzone) / usable if usable > 0 else 0.0
    curved = normalized ** exponent
    return curved * usable * (1 if raw >= 0 else -1)


class CursorController:
    def __init__(
        self,
        sensitivity: float = SENSITIVITY,
        smoothing_alpha: float = SMOOTHING_ALPHA,
        deadzone_radius: float = DEADZONE_RADIUS,
        acceleration_expo: float = ACCELERATION_EXPO,
        failsafe_enabled: bool = True,
    ) -> None:
        self.sensitivity = sensitivity
        self.smoothing_alpha = smoothing_alpha
        self.deadzone_radius = deadzone_radius
        self.acceleration_expo = acceleration_expo
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

        curved_dx = _apply_curve(raw_dx, self.deadzone_radius, self.acceleration_expo)
        curved_dy = _apply_curve(raw_dy, self.deadzone_radius, self.acceleration_expo)

        # EMA smoothing on the curved values
        a = self.smoothing_alpha
        self._smoothed_dx = a * curved_dx + (1 - a) * self._smoothed_dx
        self._smoothed_dy = a * curved_dy + (1 - a) * self._smoothed_dy

        px = self._smoothed_dx * self.sensitivity * self._screen_w
        py = self._smoothed_dy * self.sensitivity * self._screen_h

        if px != 0.0 or py != 0.0:
            pyautogui.moveRel(px, py, _pause=False)
