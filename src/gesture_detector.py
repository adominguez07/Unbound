import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

# --- Tuning constants ---
# Raise trigger to make a gesture harder to fire; lower it to make it easier.
# Release must always be below trigger (hysteresis prevents flicker).

TRIGGER_WINK_LEFT     = 0.60
TRIGGER_WINK_RIGHT    = 0.60
TRIGGER_MOUTH_OPEN    = 0.50
TRIGGER_SMILE         = 0.55
TRIGGER_PUCKER        = 0.80
TRIGGER_EYEBROW_RAISE = 0.80
TRIGGER_CHEEK_PUFF    = 0.40

RELEASE_WINK_LEFT     = 0.25
RELEASE_WINK_RIGHT    = 0.25
RELEASE_MOUTH_OPEN    = 0.30
RELEASE_SMILE         = 0.35
RELEASE_PUCKER        = 0.30
RELEASE_EYEBROW_RAISE = 0.25
RELEASE_CHEEK_PUFF    = 0.25

# When detecting a wink, the other eye must stay below this or it counts as a full blink.
BLINK_CROSS_EYE_MAX = 0.40

# Activations held longer than this become a hold instead of a tap (milliseconds).
HOLD_DURATION_MS = 750

# Winks released faster than this are treated as accidental blinks and ignored.
# A normal blink is ~150-400 ms; raise this if blinks still trigger clicks.
MIN_WINK_TAP_MS = 350
# ------------------------


class _State(Enum):
    IDLE   = auto()
    ACTIVE = auto()


@dataclass
class _GestureConfig:
    trigger: float
    release: float


@dataclass
class _GestureStatus:
    state: _State = _State.IDLE
    activated_at_ms: float = 0.0


class GestureDetector:
    """
    Converts per-frame blendshape scores into discrete tap/hold events.

    Callbacks:
        on_tap(gesture_name)        — short activation (< HOLD_DURATION_MS)
        on_hold_start(gesture_name) — activation crossed the hold threshold
        on_hold_end(gesture_name)   — held gesture released
    """

    _CONFIGS: dict[str, _GestureConfig] = {
        "wink_left":     _GestureConfig(TRIGGER_WINK_LEFT,     RELEASE_WINK_LEFT),
        "wink_right":    _GestureConfig(TRIGGER_WINK_RIGHT,    RELEASE_WINK_RIGHT),
        "mouth_open":    _GestureConfig(TRIGGER_MOUTH_OPEN,    RELEASE_MOUTH_OPEN),
        "smile":         _GestureConfig(TRIGGER_SMILE,         RELEASE_SMILE),
        "pucker":        _GestureConfig(TRIGGER_PUCKER,        RELEASE_PUCKER),
        "eyebrow_raise": _GestureConfig(TRIGGER_EYEBROW_RAISE, RELEASE_EYEBROW_RAISE),
        "cheek_puff":    _GestureConfig(TRIGGER_CHEEK_PUFF,    RELEASE_CHEEK_PUFF),
    }

    def __init__(
        self,
        on_tap: Callable[[str], None],
        on_hold_start: Callable[[str], None],
        on_hold_end: Callable[[str], None],
        hold_duration_ms: int = HOLD_DURATION_MS,
    ) -> None:
        self._on_tap = on_tap
        self._on_hold_start = on_hold_start
        self._on_hold_end = on_hold_end
        self._hold_duration_ms = hold_duration_ms

        self._status: dict[str, _GestureStatus] = {
            name: _GestureStatus() for name in self._CONFIGS
        }
        self._hold_fired: set[str] = set()

    def _score(self, name: str, bs: dict[str, float]) -> float:
        if name == "wink_left":
            left  = bs.get("eyeBlinkLeft",  0.0)
            right = bs.get("eyeBlinkRight", 0.0)
            return left if right < BLINK_CROSS_EYE_MAX else 0.0
        if name == "wink_right":
            right = bs.get("eyeBlinkRight", 0.0)
            left  = bs.get("eyeBlinkLeft",  0.0)
            return right if left < BLINK_CROSS_EYE_MAX else 0.0
        if name == "mouth_open":
            return bs.get("jawOpen", 0.0)
        if name == "smile":
            return (bs.get("mouthSmileLeft", 0.0) + bs.get("mouthSmileRight", 0.0)) / 2.0
        if name == "pucker":
            return bs.get("mouthPucker", 0.0)
        if name == "eyebrow_raise":
            return bs.get("browInnerUp", 0.0)
        if name == "cheek_puff":
            return bs.get("cheekPuff", 0.0)
        return 0.0

    def update(self, blendshapes: dict[str, float]) -> None:
        now_ms = time.monotonic() * 1000.0

        for name, cfg in self._CONFIGS.items():
            status = self._status[name]
            score  = self._score(name, blendshapes)

            if status.state is _State.IDLE:
                if score >= cfg.trigger:
                    status.state = _State.ACTIVE
                    status.activated_at_ms = now_ms

            else:  # ACTIVE
                held_ms = now_ms - status.activated_at_ms

                if name not in self._hold_fired and held_ms >= self._hold_duration_ms:
                    self._hold_fired.add(name)
                    self._on_hold_start(name)

                if score < cfg.release:
                    if name in self._hold_fired:
                        self._on_hold_end(name)
                        self._hold_fired.discard(name)
                    else:
                        # Winks require a minimum hold time to filter out involuntary blinks.
                        is_wink = name in ("wink_left", "wink_right")
                        if not is_wink or held_ms >= MIN_WINK_TAP_MS:
                            self._on_tap(name)
                    status.state = _State.IDLE
