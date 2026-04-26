import threading
from typing import TYPE_CHECKING

import pyautogui
import pyperclip

if TYPE_CHECKING:
    from .action_dispatcher import ActionDispatcher

# --- Voice command → action mapping ---
# Checked longest-phrase-first so "double click" always beats "left click".
SPEECH_COMMANDS: dict[str, str] = {
    "dictation off":  "dictation_off",
    "dictation on":   "dictation_on",
    "double click":   "double_click",
    "right click":    "right_click",
    "scroll down":    "scroll_down",
    "scroll up":      "scroll_up",
    "open keyboard":  "open_osk",
    "left click":     "left_click",
    "keyboard":       "open_osk",
    "drag":           "drag_start",
    "drop":           "drag_end",
    "pause":          "pause_tracking",
    "resume":         "pause_tracking",
}

SPEECH_SCROLL_LINES = 10
LISTEN_TIMEOUT    = 1.5   # seconds to wait before re-looping
PHRASE_TIME_LIMIT = 4.0   # max seconds per phrase (longer for dictation)
# --------------------------------------


class SpeechController:
    """
    Background thread that listens for voice commands and fires actions.

    Two typing modes:
      - Say "type [text]"       → pastes that text immediately (one-shot).
      - Say "dictation on"      → enters dictation mode; everything said is
                                  pasted as text until "dictation off".

    While active, sets dispatcher.speech_mode = True so gesture-based
    actions are suppressed — face tracking still moves the cursor.
    """

    def __init__(self, dispatcher: "ActionDispatcher") -> None:
        self._dispatcher = dispatcher
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._dragging = False
        self._dictation_mode = False

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.active:
            return
        try:
            import speech_recognition  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "SpeechRecognition is not installed. "
                "Run: python -m pip install SpeechRecognition pyaudio"
            )
        self._dispatcher.speech_mode = True
        self._dictation_mode = False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="speech")
        self._thread.start()
        print("[speech] started")

    def stop(self) -> None:
        self._stop.set()
        self._dispatcher.speech_mode = False
        self._dictation_mode = False
        if self._dragging:
            pyautogui.mouseUp()
            self._dragging = False
        print("[speech] stopped")

    # ------------------------------------------------------------------

    def _loop(self) -> None:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        mic = sr.Microphone()

        print("[speech] calibrating for ambient noise (1 s)...")
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[speech] ready — listening")

        while not self._stop.is_set():
            try:
                with mic as source:
                    audio = recognizer.listen(
                        source,
                        timeout=LISTEN_TIMEOUT,
                        phrase_time_limit=PHRASE_TIME_LIMIT,
                    )
                text = recognizer.recognize_google(audio).lower().strip()
                print(f"[speech] heard: {text!r}")
                self._handle(text)
            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except sr.RequestError as exc:
                print(f"[speech] recognition error: {exc}")

    def _handle(self, text: str) -> None:
        # Dictation mode: type everything except the stop command.
        if self._dictation_mode:
            if "dictation off" in text:
                self._dictation_mode = False
                print("[speech] dictation off")
            else:
                self._type_text(text)
            return

        # One-shot typing: "type hello world" → pastes "hello world".
        if text.startswith("type "):
            self._type_text(text[5:])
            return

        # Normal command matching (longest phrase first to avoid false hits).
        for phrase in sorted(SPEECH_COMMANDS, key=len, reverse=True):
            if phrase in text:
                action = SPEECH_COMMANDS[phrase]
                print(f"[speech] command: {phrase!r} -> {action}")
                self._fire(action)
                return

    def _fire(self, action: str) -> None:
        if action == "dictation_on":
            self._dictation_mode = True
            print("[speech] dictation on — say 'dictation off' to stop")
        elif action == "dictation_off":
            self._dictation_mode = False
            print("[speech] dictation off")
        elif action == "drag_start":
            if not self._dragging:
                pyautogui.mouseDown()
                self._dragging = True
        elif action == "drag_end":
            if self._dragging:
                pyautogui.mouseUp()
                self._dragging = False
        elif action in ("scroll_up", "scroll_down"):
            direction = SPEECH_SCROLL_LINES if action == "scroll_up" else -SPEECH_SCROLL_LINES
            pyautogui.scroll(direction)
        else:
            self._dispatcher.execute(action)

    def _type_text(self, text: str) -> None:
        """Paste text via clipboard — handles spaces, punctuation, and unicode."""
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        print(f"[speech] typed: {text!r}")
