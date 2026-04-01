"""CLI entry point for spoofjst.

Usage:
    sudo python -m spoofjst [--port PORT] [--host HOST] [--no-browser]

Pi Zero mode (headless, binds all interfaces, no browser):
    sudo python -m spoofjst --host 0.0.0.0 --port 80 --no-browser
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import sys
import webbrowser

import uvicorn

from spoofjst.config import DEFAULT_HOST, DEFAULT_PORT


def _is_pi() -> bool:
    """Detect if running on a Raspberry Pi."""
    try:
        with open("/proc/device-tree/model") as f:
            return "raspberry pi" in f.read().lower()
    except FileNotFoundError:
        return False


def main() -> None:
    on_pi = _is_pi()

    # Smart defaults: on Pi, bind all interfaces on port 80 with no browser
    default_host = "0.0.0.0" if on_pi else DEFAULT_HOST
    default_port = 80 if on_pi else DEFAULT_PORT

    parser = argparse.ArgumentParser(
        prog="spoofjst",
        description="iPhone GPS location spoofer over USB",
    )
    parser.add_argument("--port", type=int, default=default_port, help=f"Server port (default: {default_port})")
    parser.add_argument("--host", default=default_host, help=f"Server host (default: {default_host})")
    parser.add_argument("--no-browser", action="store_true", default=on_pi, help="Don't auto-open browser")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Warn if not running as root (tunnel creation requires it for iOS 17+)
    if os.geteuid() != 0:
        print("\n⚠  spoofjst needs root privileges for iOS 17+ tunnel creation.")
        print("   Re-run with: sudo python -m spoofjst\n")
        sys.exit(1)

    if on_pi:
        print("\n🍓 spoofjst v0.1.0 — Pi Zero mode")
        print("   Connect your iPhone via USB (OTG adapter)")
        print("   Join WiFi 'spoofjst' from your phone")
        print(f"   Then open http://192.168.4.1 in Safari\n")
    else:
        url = f"http://{args.host}:{args.port}"
        if not args.no_browser:
            import threading
            threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        print(f"\n🔌 spoofjst v0.1.0 — plug in your iPhone and spoof away!")
        print(f"   Open {url} in your browser\n")

    uvicorn.run(
        "spoofjst.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
