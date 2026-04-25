from typing import Callable
import pyautogui

# --- Hardcoded bindings (edit these to test different gesture → action mappings) ---
GESTURE_BINDINGS: dict[str, str] = {
    "wink_left":     "left_click",
    "wink_right":    "right_click",
    "mouth_open":    "double_click",
    "smile":         "none",
    "pucker":        "scroll_up",
    "eyebrow_raise": "pause_tracking",
    "cheek_puff":    "scroll_down",
}

# Lines scrolled per scroll event
SCROLL_LINES = 3
# ------------------------------------------------------------------------------------


class ActionDispatcher:
    def __init__(
        self,
        bindings: dict[str, str] = GESTURE_BINDINGS,
        on_pause_toggle: Callable[[], None] | None = None,
    ) -> None:
        self._bindings = dict(bindings)
        self._on_pause_toggle = on_pause_toggle

    def on_tap(self, gesture: str) -> None:
        action = self._bindings.get(gesture, "none")
        print(f"[tap]  {gesture:<16} -> {action}")
        self._execute(action, held=False)

    def on_hold_start(self, gesture: str) -> None:
        action = self._bindings.get(gesture, "none")
        print(f"[hold] {gesture:<16} -> {action}  START")
        if action == "drag_toggle":
            pyautogui.mouseDown()
        elif action == "scroll_up":
            pyautogui.scroll(SCROLL_LINES)
        elif action == "scroll_down":
            pyautogui.scroll(-SCROLL_LINES)

    def on_hold_end(self, gesture: str) -> None:
        action = self._bindings.get(gesture, "none")
        print(f"[hold] {gesture:<16} -> {action}  END")
        if action == "drag_toggle":
            pyautogui.mouseUp()

    def _execute(self, action: str, *, held: bool) -> None:
        if action == "left_click":
            pyautogui.click()
        elif action == "right_click":
            pyautogui.rightClick()
        elif action == "double_click":
            pyautogui.doubleClick()
        elif action == "scroll_up":
            pyautogui.scroll(SCROLL_LINES)
        elif action == "scroll_down":
            pyautogui.scroll(-SCROLL_LINES)
        elif action == "pause_tracking":
            if self._on_pause_toggle:
                self._on_pause_toggle()
