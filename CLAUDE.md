# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**Project Name:** NoseCursor (working title)
**Event:** Hackabull 2026 — USF 24-hour hackathon
**Track:** Accessibility

A desktop application that enables paralyzed individuals (and users with limited mobility) to control their computer's mouse using face tracking. The user's **nose tip acts as a joystick** to move the cursor, and **customizable facial gestures** (wink, mouth open, eyebrow raise, etc.) trigger mouse actions like left click, right click, double click, scroll, and drag.

The core design principle is **customization-first**: any action can be remapped to any gesture, because no two users have the same physical capabilities. A user with one eye, facial paralysis on one side, or limited muscle control must be able to configure the system to work for *them*.

## Tech Stack

- **Language:** Python 3.11+
- **Computer Vision:** OpenCV (camera capture, frame processing)
- **Face Landmarks:** MediaPipe Tasks API (`mediapipe.tasks`) — **NOT** the legacy `mediapipe.solutions` API
- **Mouse Control:** PyAutoGUI
- **Settings UI Backend:** FastAPI (serves a local web-based settings panel on `127.0.0.1`)
- **Settings UI Frontend:** Plain HTML/CSS/JS served by FastAPI (keep it lightweight for hackathon scope)
- **Native Desktop Window:** PyWebView — wraps the FastAPI-served UI in a native OS window so the app feels like a real desktop application, not a browser tab
- **Packaging:** PyInstaller — bundles the entire app (Python interpreter, dependencies, model file, UI assets) into a single `NoseCursor.exe` for the demo

## Distribution Model

The final deliverable is a Windows `.exe`. The user (or a hackathon judge) double-clicks `NoseCursor.exe` and a native window opens — no terminal, no browser, no Python install required on their machine. Internally:

1. The `.exe` starts the FastAPI server on `127.0.0.1` at an arbitrary free port (do not hardcode 8000 — it may be taken on the judge's laptop).
2. The face tracker starts on a background thread.
3. PyWebView opens a native window pointed at `http://127.0.0.1:<port>/`.
4. Closing the PyWebView window shuts down the tracker and the server cleanly.

Keep the FastAPI/HTML separation intact — it's still ideal for development (you can hit the UI in a regular browser while iterating) and PyWebView just becomes the production wrapper.

## CRITICAL: MediaPipe API Requirements

**Do NOT use `mediapipe.solutions.face_mesh`** — it is the deprecated legacy API.

Use the **MediaPipe Tasks API** instead:

```python
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# Load the FaceLandmarker task
base_options = mp_python.BaseOptions(model_asset_path='face_landmarker.task')
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,  # use VIDEO mode for webcam streams
    num_faces=1,
    output_face_blendshapes=True,        # REQUIRED — blendshapes drive gesture detection
    output_facial_transformation_matrixes=False,
)
landmarker = vision.FaceLandmarker.create_from_options(options)
```

The `face_landmarker.task` model file must be downloaded from Google's MediaPipe model zoo and placed in the `models/` directory. Do not commit the model file — add it to `.gitignore` and document the download in the README.

**Why blendshapes matter:** MediaPipe's blendshape outputs (e.g. `eyeBlinkLeft`, `eyeBlinkRight`, `jawOpen`, `mouthPucker`, `browInnerUp`) give us normalized 0.0–1.0 scores per gesture. This is far more reliable than computing eye/mouth aspect ratios manually from raw landmarks, and it's what makes customizable gestures feasible in 24 hours.

## File Structure

```
nose-cursor/
├── CLAUDE.md                       # This file
├── README.md                       # User-facing setup instructions
├── requirements.txt                # Pinned Python dependencies
├── .gitignore                      # Exclude models/, __pycache__, venv, build/, dist/
├── main.py                         # Entry point — launches tracker + FastAPI + PyWebView
├── nose_cursor.spec                # PyInstaller build spec
│
├── models/
│   └── face_landmarker.task        # (gitignored) downloaded MediaPipe model
│
├── config/
│   └── default_settings.json       # Default gesture mappings + sensitivity values
│
├── src/
│   ├── __init__.py
│   ├── tracker.py                  # Camera loop + MediaPipe FaceLandmarker
│   ├── cursor_controller.py        # Nose-to-cursor mapping + smoothing
│   ├── gesture_detector.py         # Blendshape → gesture event detection
│   ├── action_dispatcher.py        # Maps gesture events → PyAutoGUI actions
│   ├── settings_manager.py         # Load/save/validate user settings
│   ├── calibration.py              # Per-user neutral-face baseline calibration
│   ├── server.py                   # FastAPI app for the settings UI
│   ├── desktop_window.py           # PyWebView window that hosts the FastAPI UI
│   └── resource_paths.py           # Resolves asset paths for both dev and frozen .exe runs
│
└── ui/
    ├── index.html                  # Settings panel
    ├── style.css
    └── app.js                      # Talks to FastAPI endpoints
```

## Per-File Responsibilities

### `main.py`
The entry point. Responsibilities:
- Parse CLI args (e.g. `--camera 0`, `--browser` to skip PyWebView and use a regular browser for dev).
- Load settings via `SettingsManager`.
- Pick a free local port (use `socket` to bind port 0 and read back what the OS assigned).
- Start the FastAPI server in a background daemon thread on that port.
- Start the face tracker on its own background daemon thread (PyWebView wants the main thread on Windows).
- Open the PyWebView window via `desktop_window.launch(url)` on the main thread — this call blocks until the window closes.
- On window close: signal both background threads to stop, release the camera, close the FaceLandmarker, exit cleanly.
- If `--browser` is passed, skip PyWebView and just print the URL — useful while iterating on the UI.

### `src/tracker.py`
Owns the camera and MediaPipe pipeline.
- `class FaceTracker`:
  - `__init__(model_path, camera_index)` — opens `cv2.VideoCapture`, initializes the `vision.FaceLandmarker` in `RunningMode.VIDEO`.
  - `process_frame() -> FrameResult | None` — reads one frame, converts BGR→RGB, wraps in `mp.Image`, calls `landmarker.detect_for_video(image, timestamp_ms)`, returns a structured result containing nose tip coordinates and the blendshape dictionary.
  - `release()` — clean teardown.
- `FrameResult` is a small dataclass: `nose_tip: tuple[float, float]`, `blendshapes: dict[str, float]`, `frame: np.ndarray` (for optional preview).
- The nose tip landmark in MediaPipe's 478-point face mesh is **landmark index 1** (tip of nose). Use that.
- Track timestamps in milliseconds for `detect_for_video`. Use `time.monotonic_ns() // 1_000_000` or similar.

### `src/cursor_controller.py`
Converts nose position to cursor movement.
- `class CursorController`:
  - Reads sensitivity, deadzone, smoothing factor, and movement mode from settings.
  - **Two movement modes**, user-selectable:
    - `"absolute"` — face region maps directly to screen region (good for short ranges).
    - `"joystick"` — distance from neutral baseline = velocity vector applied each frame (better for limited head mobility; this should be the default for accessibility).
  - Applies an **exponential moving average** smoothing filter to reduce jitter: `smoothed = alpha * new + (1 - alpha) * smoothed`.
  - Applies a **deadzone** around the neutral baseline so tiny involuntary movements don't drift the cursor.
  - Calls `pyautogui.moveTo(x, y)` or `pyautogui.moveRel(dx, dy)`.
- **Important:** call `pyautogui.FAILSAFE = False` only after warning the user — the failsafe normally stops the program if the cursor hits a screen corner. For an accessibility tool that intentionally moves the cursor everywhere, this can fire accidentally. Make it a setting, default to `True` (safer) but allow disabling.

### `src/gesture_detector.py`
Converts blendshape scores into discrete gesture events.
- `class GestureDetector`:
  - Takes the blendshape dict each frame.
  - For each configured gesture, applies a **threshold + debounce + state machine** to avoid double-firing:
    - Gesture is `IDLE` until score crosses `trigger_threshold`.
    - Transitions to `ACTIVE`, fires a `GESTURE_START` event.
    - Stays `ACTIVE` until score drops below `release_threshold` (hysteresis prevents flicker).
    - On release, fires `GESTURE_END` event.
  - Distinguishes **taps** (short activation → click) from **holds** (long activation → drag) using a configurable hold duration.
- Supported gestures (each maps to a MediaPipe blendshape key):
  - `wink_left` → `eyeBlinkLeft` (with check that `eyeBlinkRight` is low, to distinguish from a full blink)
  - `wink_right` → `eyeBlinkRight` (symmetric check)
  - `mouth_open` → `jawOpen`
  - `smile` → `mouthSmileLeft` + `mouthSmileRight` averaged
  - `pucker` → `mouthPucker`
  - `eyebrow_raise` → `browInnerUp`
  - `cheek_puff` → `cheekPuff`
- Each gesture's threshold should be **per-user calibrated**, not hardcoded — see `calibration.py`.

### `src/action_dispatcher.py`
Bridges gesture events to PyAutoGUI actions.
- `class ActionDispatcher`:
  - Holds the user's gesture→action mapping from settings.
  - On `GESTURE_START` / `GESTURE_END` events, looks up the bound action and executes it.
- Supported actions:
  - `left_click` → `pyautogui.click()`
  - `right_click` → `pyautogui.rightClick()`
  - `double_click` → `pyautogui.doubleClick()`
  - `scroll_up` / `scroll_down` → `pyautogui.scroll(±n)` (continuous while gesture held)
  - `drag_toggle` → on `GESTURE_START` call `pyautogui.mouseDown()`, on `GESTURE_END` call `pyautogui.mouseUp()`
  - `pause_tracking` → toggles a flag that freezes the cursor controller (essential — user must be able to disable tracking to take a break)
  - `none` → unbound (lets users disable a gesture entirely if it triggers accidentally for them)
- Mapping is just a dict: `{"wink_left": "left_click", "wink_right": "right_click", "mouth_open": "double_click", ...}`.

### `src/settings_manager.py`
Persistent user configuration.
- Loads `config/default_settings.json` on first run, copies to `~/.nose_cursor/settings.json` for persistence.
- `class SettingsManager`:
  - `get(key)` / `set(key, value)` / `save()` / `load()`.
  - Validates types and ranges (e.g. thresholds must be 0.0–1.0).
  - Emits an event/callback when settings change so the tracker hot-reloads without restart.
- Settings schema includes:
  - `camera_index`
  - `movement_mode` (`"absolute"` | `"joystick"`)
  - `sensitivity` (float)
  - `smoothing_alpha` (0.0–1.0)
  - `deadzone_radius` (pixels or normalized)
  - `gesture_bindings` (dict described above)
  - `gesture_thresholds` (per-gesture trigger/release values)
  - `hold_duration_ms` (tap vs. hold cutoff)
  - `failsafe_enabled` (bool)

### `src/calibration.py`
First-run and on-demand calibration.
- `class Calibrator`:
  - `capture_neutral(duration_seconds=3)` — records the user's resting face for N seconds, averages nose position and all blendshape scores → that's the personal baseline.
  - `capture_gesture(gesture_name, duration_seconds=2)` — asks user to perform a gesture, records peak blendshape score, sets thresholds at e.g. 60% of peak (trigger) and 30% of peak (release).
  - Saves results into `SettingsManager`.
- Critical for accessibility: a user with facial asymmetry might only reach `eyeBlinkLeft = 0.4` at maximum, where the default threshold of 0.5 would never fire.

### `src/server.py`
FastAPI backend for the settings UI.
- Serves the static UI from `ui/` at `GET /`.
- REST endpoints:
  - `GET /api/settings` → current settings JSON
  - `POST /api/settings` → update settings (validated, hot-reloaded)
  - `GET /api/blendshapes` → live blendshape values (for the UI to show real-time bars while user adjusts thresholds)
  - `POST /api/calibrate/neutral` → trigger neutral calibration
  - `POST /api/calibrate/gesture/{name}` → trigger per-gesture calibration
  - `POST /api/pause` / `POST /api/resume` → control tracking
  - `POST /api/quit` → triggers a clean shutdown (the window's "X" button hits this)
- Use a shared state object (a single `AppState` instance passed to both the tracker and the FastAPI app) for cross-thread communication. Wrap mutable shared data in a `threading.Lock`.
- Run with `uvicorn` programmatically from `main.py`, not via the CLI, so it can share process state with the tracker.
- Bind to `127.0.0.1` only — never `0.0.0.0`. This is a local desktop app; nothing should be reachable from the network.
- Use the path resolver from `resource_paths.py` when locating the `ui/` directory so static files work both in dev and in the bundled `.exe`.

### `src/desktop_window.py`
PyWebView wrapper that hosts the FastAPI UI in a native OS window.
- `launch(url: str, app_state: AppState) -> None`:
  - Calls `webview.create_window(title="NoseCursor", url=url, width=1000, height=700, min_size=(800, 600))`.
  - Calls `webview.start()` (blocking — runs the native event loop on the main thread).
  - On window close, sets `app_state.shutdown_requested = True` so the tracker thread exits its loop.
- Use the default GUI backend on Windows (EdgeChromium / WebView2). WebView2 ships with Windows 11 by default — no extra install needed on the demo machine, but note it in the README for any judge running Windows 10.
- Do not enable `webview.start(debug=True)` in the bundled `.exe`. Only in dev.

### `src/resource_paths.py`
Path resolution that works in both dev and frozen-`.exe` mode.
- PyInstaller unpacks bundled assets into a temp directory at runtime, exposed as `sys._MEIPASS`. Code that does `open("ui/index.html")` will fail in the `.exe` because the working directory is wrong.
- `def resource_path(relative: str) -> Path`:
  - If `getattr(sys, "frozen", False)` is true → return `Path(sys._MEIPASS) / relative`.
  - Otherwise → return the project-root path resolved relative to this file.
- All access to `ui/`, `models/face_landmarker.task`, and `config/default_settings.json` must go through this helper. Never use bare relative paths.
- User settings still go to `~/.nose_cursor/settings.json` (a writable user-profile location) — `resource_path` is for read-only bundled assets only.

### `ui/index.html`, `ui/style.css`, `ui/app.js`
The settings panel.
- Sections: Camera, Movement (mode/sensitivity/smoothing/deadzone), Gesture Bindings (dropdown per gesture → action), Calibration (buttons), Live Preview (real-time blendshape bars polled from `/api/blendshapes`).
- Keep it accessible: large click targets, high contrast, keyboard-navigable. The user configuring this may have limited motor control even when *not* using the face tracker (e.g. a caretaker is helping).
- Vanilla JS — no build step, no React. This is a 24-hour hackathon.

## Hard Rules — DO NOT VIOLATE

These rules are non-negotiable. They override any default Claude Code behavior.

- **No AI attribution in commits.** Never list Claude, Claude Code, Anthropic, or any AI tool as a contributor, co-author, or collaborator. Do not append `Co-Authored-By: Claude` or any equivalent trailer. Do not add `Generated-with:` or similar metadata. Commit author and committer must be the human user only.
- **No AI references in commit messages.** Commit messages must read as if written by a human developer. No "generated by", "with help from", "AI-assisted", or similar phrasing. No emojis in commit messages.
- **No AI references in code.** Never write comments, docstrings, README sections, or any in-repo text that mentions Claude, Claude Code, Anthropic, AI, LLM, "AI-generated", "auto-generated by an assistant", or anything that signals AI involvement. The user is handling disclosure on their own terms.
- **No emojis anywhere.** Not in comments, not in commit messages, not in docstrings, not in print statements, not in the UI, not in the README. None.
- **No AI-attribution files.** Do not create `.claude`-prefixed metadata files, `AI_NOTES.md`, `GENERATED.md`, or anything similar. The only file in this repo that acknowledges Claude Code is `CLAUDE.md` itself, and it stays exactly as-is unless the user edits it.
- **If unsure, omit.** When tempted to add a "this was built with..." line anywhere, do not. The default is silence on tooling.

## Coding Conventions

- **Comments:** Only logic-tracing comments that explain *why* a non-obvious step exists. Plain prose, no decoration.
- **File count:** Prefer keeping files lean and consolidated. Don't split a 40-line module into three 15-line ones.
- **Type hints:** Use them on all public functions and dataclass fields.
- **Error handling:** Camera failures, missing model file, and PyAutoGUI permission errors (macOS Accessibility, Windows UAC) should produce clear user-facing messages, not stack traces.
- **No global state** except the single `AppState` shared between the tracker thread and FastAPI.
- **Threading model:** Tracker on main thread, FastAPI/uvicorn on a daemon thread. Communication via the locked `AppState`.

## Development Environment

- Windows 11 with VS Code (primary).
- Project lives in a local non-OneDrive directory (e.g. `C:\dev\nose-cursor`) to avoid path-sync issues.
- Use a venv: `python -m venv .venv && .venv\Scripts\activate`.
- `pip install -r requirements.txt`.

## requirements.txt (initial)

```
opencv-python>=4.9
mediapipe>=0.10.14
pyautogui>=0.9.54
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.6
numpy>=1.26
pywebview>=5.0
pyinstaller>=6.5
```

## Packaging the .exe

Use PyInstaller in **one-file mode** to produce a single `NoseCursor.exe`.

A `nose_cursor.spec` file should live at the repo root. Key requirements for the spec:

- `Analysis(...)` must include `datas=[...]` entries that bundle:
  - `ui/` → `ui` (so HTML/CSS/JS are inside the `.exe`)
  - `models/face_landmarker.task` → `models` (so the user doesn't have to download it)
  - `config/default_settings.json` → `config`
- `hiddenimports` must include MediaPipe and uvicorn submodules that PyInstaller's static analysis misses. Common ones: `uvicorn.logging`, `uvicorn.loops.auto`, `uvicorn.protocols.http.auto`, `uvicorn.protocols.websockets.auto`, `uvicorn.lifespan.on`. Add more as build errors reveal them.
- `EXE(...)` should set `console=False` so no terminal window appears when judges launch the app.
- `onefile=True`, `name="NoseCursor"`.
- Optional: `icon="assets/icon.ico"` for a real app icon.

Build command:
```
pyinstaller nose_cursor.spec --clean --noconfirm
```
Output lands in `dist/NoseCursor.exe`.

**Test the bundled `.exe` on a clean Windows machine before the demo.** PyInstaller bugs (missing hidden imports, broken paths) only surface outside your dev environment.

**Windows SmartScreen warning:** unsigned `.exe` files trigger "Windows protected your PC" on first launch. The judges will see "More info → Run anyway." Mention this in your demo intro so they're not surprised. Code signing is out of scope for a 24-hour hackathon.

## Build Order (24-hour hackathon plan)

Claude Code should build in this order so we have a working demo at every checkpoint:

1. **Hour 0–2:** `tracker.py` + `resource_paths.py` working standalone — opens webcam, prints nose coordinates and blendshapes to console.
2. **Hour 2–4:** `cursor_controller.py` — nose moves the cursor in joystick mode with smoothing and deadzone.
3. **Hour 4–6:** `gesture_detector.py` + `action_dispatcher.py` — a hardcoded wink-to-click works end-to-end.
4. **Hour 6–10:** `settings_manager.py` + `calibration.py` — settings load/save, neutral calibration runs.
5. **Hour 10–14:** `server.py` + `ui/` — the web settings panel works in a regular browser (use `--browser` flag), bindings are user-configurable.
6. **Hour 14–17:** `desktop_window.py` — PyWebView wraps the UI in a native window. App now feels like a desktop app.
7. **Hour 17–20:** Per-gesture calibration in the UI; live blendshape bars; polish.
8. **Hour 20–22:** PyInstaller bundle. Build `NoseCursor.exe`. Test on a clean Windows install if possible.
9. **Hour 22–24:** Demo prep, README, edge-case fixes (no face detected, camera disconnects, port already in use), submission video.

## Demo Pitch Anchors

When polishing for the accessibility track, lean on these points:
- **Universal customization** — every gesture is remappable; no assumption about what the user *can* do.
- **Per-user calibration** — thresholds adapt to the individual's range of motion, not the other way around.
- **Pause gesture** — the user controls when tracking is on, never trapped by their own input device.
- **Local-only** — no cloud, no account, no data leaves the machine. Privacy is an accessibility feature.
