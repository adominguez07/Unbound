import threading

try:
    import winsound as _winsound
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _run(fn):
    if not _AVAILABLE:
        return
    threading.Thread(target=fn, daemon=True).start()


def click():
    def _():
        try:
            _winsound.Beep(900, 35)
        except Exception:
            pass
    _run(_)


def dictation_on():
    def _():
        try:
            _winsound.Beep(750, 90)
            _winsound.Beep(1050, 110)
        except Exception:
            pass
    _run(_)


def dictation_off():
    def _():
        try:
            _winsound.Beep(1050, 90)
            _winsound.Beep(650, 110)
        except Exception:
            pass
    _run(_)
