"""Entry point: FastAPI in a background thread + a native desktop window.

Falls back to the default browser if pywebview/WebView2 is unavailable.
"""
import threading
import time
import urllib.request

import uvicorn

from . import config


def _serve(host: str, port: int):
    uvicorn.run("assistant.server:app", host=host, port=port, log_level="warning")


def _wait_until_up(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except OSError:
            time.sleep(0.3)
    return False


def main():
    config.ensure_dirs()
    app_cfg = config.CFG["app"]
    host, port = app_cfg["host"], app_cfg["port"]
    url = f"http://{host}:{port}"

    threading.Thread(target=_serve, args=(host, port), daemon=True).start()
    if not _wait_until_up(f"{url}/api/health"):
        raise SystemExit("Server failed to start — check the console for errors.")

    try:
        import webview  # pywebview must create its window on the main thread
        webview.create_window(app_cfg["window_title"], url, width=1000, height=760)
        webview.start()
    except Exception as e:
        print(f"Could not open a native window ({e}); opening in your browser instead.")
        import webbrowser
        webbrowser.open(url)
        while True:  # keep the server alive
            time.sleep(3600)


if __name__ == "__main__":
    main()
