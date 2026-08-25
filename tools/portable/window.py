#!/usr/bin/env python3
"""Open the Lucy C2 dashboard in a native desktop window via pywebview."""
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8000"


def wait_for_backend(timeout: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    if not wait_for_backend():
        print("[Lucy Window] Backend did not become ready.", file=sys.stderr)
        sys.exit(1)

    try:
        import webview
    except ImportError as exc:
        print(f"[Lucy Window] pywebview is not installed: {exc}", file=sys.stderr)
        sys.exit(1)

    webview.create_window(
        "Lucy C2",
        URL,
        width=1440,
        height=900,
        min_size=(1024, 640),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
