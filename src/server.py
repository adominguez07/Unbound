"""
FastAPI settings server for NoseCursor.

AppState is the single shared object passed between this server and the tracker
thread in main.py.  All mutable fields that cross thread boundaries are guarded
by _lock or are written only from one thread.
"""

import asyncio
import threading
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .resource_paths import resource_path
from .settings_manager import SettingsManager


class AppState:
    """Thread-safe bridge between the tracker loop and the settings server."""

    def __init__(self, settings: SettingsManager) -> None:
        self.settings = settings

        # Populated by main.py after each component starts
        self.tracker = None
        self.calibrator = None
        self.cursor = None

        self._lock = threading.Lock()
        self._blendshapes: dict[str, float] = {}

        self.is_paused: bool = False
        self.shutdown_requested: bool = False
        self.calibration_in_progress: bool = False

    def update_blendshapes(self, bs: dict[str, float]) -> None:
        with self._lock:
            self._blendshapes = dict(bs)

    def get_blendshapes(self) -> dict[str, float]:
        with self._lock:
            return dict(self._blendshapes)


def create_app(state: AppState) -> FastAPI:
    app = FastAPI(title="NoseCursor")
    ui_dir = resource_path("ui")

    app.mount("/static", StaticFiles(directory=str(ui_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (ui_dir / "index.html").read_text(encoding="utf-8")

    # --- Settings ---

    @app.get("/api/settings")
    async def get_settings():
        return state.settings.get_all()

    @app.post("/api/settings")
    async def post_settings(request: Request):
        try:
            patch: dict[str, Any] = await request.json()
            state.settings.update(patch)
            state.settings.save()
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"status": "ok"}

    # --- Live data ---

    @app.get("/api/blendshapes")
    async def get_blendshapes():
        return state.get_blendshapes()

    @app.get("/api/status")
    async def get_status():
        return {
            "paused": state.is_paused,
            "calibration_in_progress": state.calibration_in_progress,
        }

    # --- Calibration ---

    @app.post("/api/calibrate/neutral")
    async def calibrate_neutral():
        if state.calibrator is None:
            raise HTTPException(503, "Tracker not running yet")
        if state.calibration_in_progress:
            raise HTTPException(409, "Calibration already in progress")
        state.calibration_in_progress = True
        try:
            await asyncio.to_thread(state.calibrator.capture_neutral, 3.0)
        except RuntimeError as exc:
            raise HTTPException(500, str(exc))
        finally:
            state.calibration_in_progress = False

        # Re-center the live cursor controller so the deadzone moves to the
        # user's current head position immediately — no restart needed.
        if state.cursor is not None:
            nx = state.settings.get("neutral_nose_x")
            ny = state.settings.get("neutral_nose_y")
            if nx is not None and ny is not None:
                state.cursor.set_neutral((nx, ny))

        return {"status": "ok"}

    @app.post("/api/calibrate/gesture/{name}")
    async def calibrate_gesture(name: str):
        if state.calibrator is None:
            raise HTTPException(503, "Tracker not running yet")
        if state.calibration_in_progress:
            raise HTTPException(409, "Calibration already in progress")
        state.calibration_in_progress = True
        try:
            thresholds = await asyncio.to_thread(state.calibrator.capture_gesture, name, 2.0)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except RuntimeError as exc:
            raise HTTPException(500, str(exc))
        finally:
            state.calibration_in_progress = False
        return {"status": "ok", "thresholds": thresholds}

    # --- Tracking control ---

    @app.post("/api/pause")
    async def pause():
        state.is_paused = True
        if state.cursor is not None:
            state.cursor.paused = True
        return {"status": "paused"}

    @app.post("/api/resume")
    async def resume():
        state.is_paused = False
        if state.cursor is not None:
            state.cursor.paused = False
        return {"status": "resumed"}

    @app.post("/api/quit")
    async def quit_app():
        state.shutdown_requested = True
        return {"status": "shutting_down"}

    return app
