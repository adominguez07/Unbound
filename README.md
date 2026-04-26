# Unbound

A Windows desktop application that lets users control their mouse entirely through face movements and facial gestures. The nose tip acts as a joystick to move the cursor; customizable facial expressions trigger clicks, scrolls, drags, and more. Designed for people with limited hand or arm mobility.

Built for Hackabull 2026 — USF 24-hour hackathon, Accessibility track.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Features](#features)
- [Requirements](#requirements)
- [Setup](#setup)
- [Running the App](#running-the-app)
- [Settings UI](#settings-ui)
- [Default Gesture Bindings](#default-gesture-bindings)
- [Available Actions](#available-actions)
- [Voice Commands](#voice-commands)
- [Calibration](#calibration)
- [Movement Modes](#movement-modes)
- [Tuning Parameters](#tuning-parameters)
- [Gesture Thresholds](#gesture-thresholds)
- [Audio Feedback](#audio-feedback)
- [Settings Storage](#settings-storage)
- [Building the Executable](#building-the-executable)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## How It Works

Unbound opens your webcam and runs Google's MediaPipe face landmark model on every frame. It tracks the position of your nose tip in normalized screen space and translates movement relative to a calibrated neutral position into cursor velocity (joystick mode) or absolute screen position (absolute mode).

Separately, MediaPipe outputs 52 blendshape scores — normalized 0.0–1.0 values representing facial muscle activations such as eye blink, jaw open, smile, and lip pucker. Unbound watches these scores against per-gesture thresholds and fires mouse actions when a gesture is detected.

A settings panel served by a local FastAPI server lets you remap every gesture, tune every threshold, run calibration, and optionally enable voice commands — all while the tracker is running.

---

## Features

- **Nose-tip cursor control** — move the cursor by tilting your head
- **Six remappable facial gestures** — any gesture can be assigned any action
- **Per-user calibration** — thresholds adapt to your face and range of motion, not the other way around
- **Joystick and absolute movement modes**
- **Exponential acceleration curve** — slow and precise near center, fast at the edges
- **Tap vs. hold detection** — a quick gesture fires a tap action; holding the same gesture fires a hold action (e.g., continuous scroll or drag)
- **Drag and drop** — assign drag to any hold gesture
- **On-screen keyboard toggle** — open or close the Windows OSK with a gesture
- **Speech mode** — all mouse actions can be triggered by voice while face tracking still moves the cursor
- **Dictation mode** — say anything and it is typed at the cursor position; assignable as a gesture action
- **Audio feedback** — distinct sounds for left click, dictation start, and dictation stop
- **Hot-reload settings** — changes in the settings panel take effect immediately without restarting
- **Native desktop window** via PyWebView (no browser needed)

---

## Requirements

**Operating system:** Windows 10 or Windows 11

**Python:** 3.11 or newer

**Webcam:** any USB or built-in webcam supported by OpenCV

**PyWebView on Windows 10:** requires Microsoft WebView2 Runtime. It ships with Windows 11 by default. On Windows 10, download and install it from:
https://developer.microsoft.com/en-us/microsoft-edge/webview2/

**Speech mode only:** requires an internet connection (Google Speech API) and a microphone.

**Python dependencies** (all installable via pip):

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
SpeechRecognition>=3.10
pyaudio>=0.2.14
```

---

## Setup

### 1. Clone the repository

```
git clone <repo-url>
cd Unbound
```

### 2. Create and activate a virtual environment

```
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Download the MediaPipe face landmark model

Unbound uses MediaPipe's FaceLandmarker task model. Download it and place it at `models/face_landmarker.task`:

```
mkdir models
curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
```

The model file is around 5 MB. It is excluded from version control via `.gitignore`.

---

## Running the App

**Normal mode** (native window via PyWebView):

```
python main.py
```

**Browser mode** (opens the settings UI in your default browser — useful during development):

```
python main.py --browser
```

**Specify a camera** (if you have multiple cameras and the default is wrong):

```
python main.py --camera 1
```

On first launch, the app spends about two seconds capturing your resting face position to set the neutral baseline. Hold still and look straight at the camera during this time.

**Running as administrator:** The on-screen keyboard (OSK) and some system-level interactions require the app to be run as administrator on Windows due to User Interface Privilege Isolation (UIPI). Right-click your terminal and choose "Run as administrator" before starting the app.

---

## Settings UI

The settings panel opens automatically when the app starts. It is a web interface served locally on a random free port and displayed inside a PyWebView native window.

The panel is organized into five sections accessible from the left sidebar:

| Section | Contents |
|---|---|
| Movement | Cursor speed, smoothing, deadzone, acceleration, hold duration, camera index |
| Calibration | Neutral face calibration and per-gesture calibration |
| Gestures | Remap each gesture to any action; fine-tune trigger and release thresholds |
| Voice | Enable/disable speech mode; list of voice commands |
| Live View | Real-time blendshape score bars for tuning thresholds |

Changes are saved automatically 1.2 seconds after you stop adjusting a control and take effect in the running app immediately — no restart required.

---

## Default Gesture Bindings

| Gesture | Default Action |
|---|---|
| Left wink | Open / Close On-Screen Keyboard |
| Right wink | Right Click |
| Mouth open | Left Click |
| Smile | Scroll Down (hold) |
| Pucker / Kiss | Scroll Up (hold) |
| Eyebrow raise | Pause / Resume Tracking |

Every binding can be changed in the Gestures section of the settings panel.

---

## Available Actions

| Action | Description |
|---|---|
| Left Click | Single left click |
| Right Click | Single right click |
| Double Click | Double left click |
| Scroll Up (hold) | Scroll up continuously while gesture is held |
| Scroll Down (hold) | Scroll down continuously while gesture is held |
| Drag Toggle | Hold to drag; release to drop |
| Open On-Screen Keyboard | Toggle the Windows on-screen keyboard |
| Toggle Dictation | Start voice typing; same gesture stops it |
| Pause / Resume Tracking | Freeze or unfreeze cursor movement |
| None (disabled) | Ignore this gesture |

**Tap vs. hold:** Gestures held shorter than the Hold Duration threshold fire a tap action (click, toggle). Gestures held longer fire a hold action (scroll, drag). Scroll and drag only activate on hold.

---

## Voice Commands

Enable speech mode from the Voice section of the settings panel or by assigning "Toggle Dictation" to a gesture. When speech mode is active, all mouse actions are triggered by voice and facial gestures only move the cursor.

| Say | Action |
|---|---|
| left click | Left click |
| right click | Right click |
| double click | Double click |
| scroll up | Scroll up |
| scroll down | Scroll down |
| keyboard | Toggle on-screen keyboard |
| drag | Press and hold mouse button |
| drop | Release mouse button |
| pause | Pause tracking |
| resume | Resume tracking |
| type [text] | Type the words that follow immediately |
| dictation on | Enter dictation mode — everything said is typed |
| dictation off | Exit dictation mode, return to voice commands |

Speech recognition uses the Google Speech API and requires an active internet connection. PyAudio is required for microphone access.

**Dictation mode as a gesture:** Assign "Toggle Dictation" to any gesture. One activation starts speech recognition and immediately enters dictation mode. A second activation of the same gesture stops it entirely.

---

## Calibration

Calibration is strongly recommended on first run. Without it, the app uses default thresholds that may not match your face.

### Neutral calibration

Hold your face still and relaxed, then click "Calibrate Neutral Face (3 s)" in the Calibration section. The app records your resting nose position and blendshape baseline. The cursor deadzone will re-center to your current head position after this completes.

### Per-gesture calibration

For each gesture, click its button in the Per-Gesture Calibration grid, then perform the gesture clearly and hold it for 2 seconds. The app measures the peak blendshape score for that gesture and sets the trigger threshold to 65% of that peak and the release threshold to 35%. This ensures the gesture fires reliably for you specifically.

**Why calibration matters:** A user who can only blink one eye to a score of 0.4 will never reach the default trigger of 0.6. Calibration removes this barrier.

---

## Movement Modes

### Joystick (default)

The distance your nose is from its neutral (resting) position is mapped to cursor velocity. The further you tilt, the faster the cursor moves. This is the recommended mode for users with limited head mobility because you never need to reach the edges of the screen — you only need to hold a tilt.

### Absolute

Your face region maps directly to the screen. Looking left moves the cursor toward the left edge of the screen; looking right moves it toward the right edge. Similar to a touchpad.

---

## Tuning Parameters

All parameters are adjustable in the Movement section of the settings panel.

| Parameter | Default | Effect |
|---|---|---|
| Sensitivity | 0.05 | Scales cursor velocity. Higher = faster cursor for the same head tilt. |
| Smoothing | 0.35 | Exponential moving average weight for each new frame. Lower = smoother but laggier; higher = more responsive but jittery. |
| Deadzone | 0.03 | Radius around neutral position where movement is ignored. Prevents involuntary micro-movements from drifting the cursor. |
| Acceleration | 0.8 | Power curve exponent applied after deadzone. 1.0 = linear. Values below 1.0 make the cursor feel lighter near the center. |
| Hold Duration | 750 ms | How long a gesture must be held before it counts as a hold (not a tap). |
| Camera Index | 0 | Which webcam to use. 0 = system default. Increment if you have multiple cameras. |
| Failsafe | On | When enabled, moving the cursor to the top-left corner of the screen immediately stops the app. Recommended to leave on. |

---

## Gesture Thresholds

Each gesture has two thresholds visible under "Threshold Fine-Tuning" in the Gestures section:

- **Trigger** — the blendshape score at which the gesture activates. Higher = harder to fire accidentally; lower = more sensitive.
- **Release** — the score the gesture must fall below to deactivate. Must always be lower than the trigger (hysteresis). This prevents flickering near the threshold.

Run per-gesture calibration to set these automatically based on your personal range of motion. You can also adjust them manually using the real-time bars in the Live View section — perform a gesture and watch the bar to find your peak score, then set the trigger to about 60–70% of that value.

---

## Audio Feedback

Unbound plays short audio tones through the system audio device to confirm certain events:

| Event | Sound |
|---|---|
| Left click (gesture or voice) | Single short tone |
| Dictation activated | Two ascending tones |
| Dictation deactivated | Two descending tones |

Audio uses the Windows `winsound` module — no additional installation required.

---

## Settings Storage

User settings are saved to:

```
C:\Users\<YourName>\.unbound\settings.json
```

This file is created automatically on first run from the bundled defaults. Deleting it resets all settings to defaults on the next launch. The app never overwrites this file without user action — clicking "Reset to Defaults" in the settings panel is the only way to revert.

---

## Building the Executable

To build a standalone `Unbound.exe` that runs without a Python installation:

```
pip install pyinstaller
pyinstaller --onefile --windowed --name Unbound --add-data "ui;ui" --add-data "models;models" --add-data "config;config" main.py
```

The output will be at `dist\Unbound.exe`.

Key notes for the PyInstaller build:
- `--windowed` suppresses the terminal window
- The `--add-data` flags bundle the UI, model file, and default settings into the executable
- `resource_paths.py` handles resolving these bundled paths at runtime via `sys._MEIPASS`

**Windows SmartScreen:** Unsigned executables trigger a "Windows protected your PC" warning on first run. Click "More info" then "Run anyway." Code signing is required to remove this warning permanently.

---

## Project Structure

```
Unbound/
├── main.py                    Entry point — starts tracker, server, and window
├── requirements.txt
├── README.md
│
├── models/
│   └── face_landmarker.task   MediaPipe model (download separately, not in repo)
│
├── config/
│   └── default_settings.json  Default values loaded on first run
│
├── src/
│   ├── tracker.py             Webcam loop and MediaPipe face landmark pipeline
│   ├── cursor_controller.py   Nose position to cursor movement with smoothing
│   ├── gesture_detector.py    Blendshape scores to tap/hold events
│   ├── action_dispatcher.py   Gesture events to PyAutoGUI mouse actions
│   ├── settings_manager.py    Load, save, validate, and hot-reload settings
│   ├── calibration.py         Neutral and per-gesture calibration routines
│   ├── server.py              FastAPI server and AppState shared object
│   ├── desktop_window.py      PyWebView wrapper for the native window
│   ├── speech_controller.py   Voice command recognition and dictation mode
│   ├── sounds.py              Audio feedback via winsound
│   └── resource_paths.py      Asset path resolution for dev and frozen .exe
│
└── ui/
    └── index.html             Settings panel (React + Babel, no build step)
```

---

## Troubleshooting

**Camera not detected**
Make sure no other application is using the webcam. Try incrementing the Camera Index in the settings panel (0, 1, 2, ...) if you have multiple cameras.

**"face_landmarker.task" not found**
The model file must be downloaded separately. See the Setup section. The file goes in the `models/` folder in the project root.

**Cursor drifts when face is still**
Run neutral calibration. The drift means the app's neutral position does not match your current resting head position.

**Gestures fire too easily or not at all**
Run per-gesture calibration for the affected gestures, or manually adjust the trigger threshold in the Threshold Fine-Tuning section while watching the Live View bars.

**Winks trigger on every blink**
Increase the trigger threshold for the wink gesture, or increase the Hold Duration so that quick involuntary blinks (under ~350 ms) are filtered out. The app already applies a minimum wink duration filter to distinguish blinks from intentional winks.

**On-screen keyboard won't close / OSK clicks don't register**
The Windows on-screen keyboard runs at an elevated privilege level (UIAccess). The app must be run as administrator to send it close messages or synthetic click events. Right-click your terminal and choose "Run as administrator."

**Speech mode: microphone not recognized or no transcription**
Ensure PyAudio is installed (`pip install pyaudio`). Check that your microphone is set as the default recording device in Windows Sound settings. Speech mode requires an internet connection — it uses Google's Speech API.

**Import errors for mediapipe or numpy in VS Code**
This is a VS Code linter issue, not a real error. The linter is using the system Python instead of the virtual environment. Open the Command Palette (Ctrl+Shift+P), run "Python: Select Interpreter", and choose the `.venv` environment inside the project folder.

**App starts but settings window is blank or fails to load**
On Windows 10, the PyWebView window requires the Microsoft WebView2 Runtime. Download and install it from the Microsoft website, then restart the app. Alternatively, run with `--browser` to use your default browser as the settings panel instead.

**Pip install fails in an administrator terminal**
The admin terminal does not inherit the virtual environment. Use the full path to the venv pip: `.venv\Scripts\python.exe -m pip install -r requirements.txt`
