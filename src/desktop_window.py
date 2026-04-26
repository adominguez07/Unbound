import time
import webbrowser


def launch(url: str, app_state) -> None:
    try:
        import webview
        window = webview.create_window(
            "NoseCursor",
            url=url,
            width=1100,
            height=750,
            min_size=(800, 600),
        )
        webview.start()
        app_state.shutdown_requested = True
    except ImportError:
        # PyWebView not installed yet — open in system browser and block until quit.
        print("PyWebView not found; opening in system browser.")
        print(f"Settings UI: {url}")
        webbrowser.open(url)
        try:
            while not app_state.shutdown_requested:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
