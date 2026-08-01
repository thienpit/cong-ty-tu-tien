#!/usr/bin/env python3
"""Launcher: mở Dashboard như desktop app (native window)."""
import threading
import time

import webview

from server import DashboardHandler, PORT, DIRECTORY


def start_server():
    import socketserver
    with socketserver.TCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(1)
    print("Starting window...")
    window = webview.create_window(
        title="🏯 Công Ty Tu Tiên — Bảng Giám Sát",
        url=f"http://localhost:{PORT}",
        width=1200,
        height=800,
        min_size=(900, 600),
    )
    print("Window created. Starting webview...")
    webview.start(debug=True)
    print("Webview started.")
