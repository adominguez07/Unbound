import threading
import time
from typing import Callable
import pyautogui

# --- Hardcoded bindings (edit these to test different gesture → action mappings) ---
GESTURE_BINDINGS: dict[str, str] = {
    "wink_left":     "left_click",
    "wink_right":    "right_click",
    "mouth_open":    "double_click",
    "smile":         "scroll_down",
    "pucker":        "scroll_up",
    "eyebrow_raise": "pause_tracking",
    "cheek_puff":    "none",
}

# Lines scrolled per tick while a scroll gesture is held
SCROLL_LINES = 20
# Seconds between each scroll tick during a hold
SCROLL_INTERVAL = 0.08
# ------------------------------------------------------------------------------------


class ActionDispatcher:
    def __init__(
        self,
        bindings: dict[str, str] = GESTURE_BINDINGS,
        on_pause_toggle: Callable[[], None] | None = None,
    ) -> None:
        self._bindings = dict(bindings)
        self._on_pause_toggle = on_pause_toggle
        # Maps gesture name → stop-event for its active scroll thread
        self._scroll_threads: dict[str, threading.Event] = {}

    def on_tap(self, gesture: str) -> None:
        action = self._bindings.get(gesture, "none")
        print(f"[tap]  {gesture:<16} -> {action}")
        if action == "left_click":
            pyautogui.click()
        elif action == "right_click":
            pyautogui.rightClick()
        elif action == "double_click":
            pyautogui.doubleClick()
        elif action == "pause_tracking":
            if self._on_pause_toggle:
                self._on_pause_toggle()

    def on_hold_start(self, gesture: str) -> None:
        action = self._bindings.get(gesture, "none")
        print(f"[hold] {gesture:<16} -> {action}  START")
        if action in ("scroll_up", "scroll_down"):
            self._start_scroll(gesture, action)
        elif action == "drag_toggle":
            pyautogui.mouseDown()

    def on_hold_end(self, gesture: str) -> None:
        action = self._bindings.get(gesture, "none")
        print(f"[hold] {gesture:<16} -> {action}  END")
        if action in ("scroll_up", "scroll_down"):
            self._stop_scroll(gesture)
        elif action == "drag_toggle":
            pyautogui.mouseUp()

    def _start_scroll(self, gesture: str, action: str) -> None:
        stop = threading.Event()
        self._scroll_threads[gesture] = stop
        direction = SCROLL_LINES if action == "scroll_up" else -SCROLL_LINES

        def _loop() -> None:
            while not stop.is_set():
                pyautogui.scroll(direction)
                time.sleep(SCROLL_INTERVAL)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def _stop_scroll(self, gesture: str) -> None:
        stop = self._scroll_threads.pop(gesture, None)
        if stop:
            stop.set()
