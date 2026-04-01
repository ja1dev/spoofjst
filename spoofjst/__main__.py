"""CLI entry point for spoofjst.

Usage:
    sudo python -m spoofjst [--port PORT] [--host HOST] [--no-browser]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import webbrowser

import uvicorn

from spoofjst.config import DEFAULT_HOST, DEFAULT_PORT


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spoofjst",
        description="iPhone GPS location spoofer over USB",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Server host (default: {DEFAULT_HOST})")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
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

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        # Open browser after a short delay to let server start
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
