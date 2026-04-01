"""iOS 17+ tunnel lifecycle management.

For iOS 17+, developer services require a privileged tunnel (TUN device)
before DVT commands like location simulation can work. This module manages
the tunnel as a subprocess of pymobiledevice3.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil

logger = logging.getLogger(__name__)


def _find_pymobiledevice3() -> str:
    """Find the pymobiledevice3 executable path."""
    path = shutil.which("pymobiledevice3")
    if path:
        return path
    # Fallback to running as python module
    return None


class TunnelManager:
    """Manages the pymobiledevice3 lockdown tunnel subprocess."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._rsd_address: str | None = None
        self._rsd_port: int | None = None
        self.status: str = "disconnected"  # disconnected | connecting | connected | error
        self._service_provider = None

    async def start(self, udid: str) -> bool:
        """Start a lockdown tunnel for the given device.

        Tries `remote start-tunnel` first, then falls back to
        `lockdown start-tunnel` (faster, available on iOS 17.4+).
        """
        await self.stop()
        self.status = "connecting"

        pmd3 = _find_pymobiledevice3()

        # Build command variants to try
        commands = []
        if pmd3:
            commands.append([pmd3, "remote", "start-tunnel", "--udid", udid, "--script-mode"])
            commands.append([pmd3, "lockdown", "start-tunnel", "--udid", udid, "--script-mode"])
        else:
            import sys
            py = sys.executable
            commands.append([py, "-m", "pymobiledevice3", "remote", "start-tunnel", "--udid", udid, "--script-mode"])
            commands.append([py, "-m", "pymobiledevice3", "lockdown", "start-tunnel", "--udid", udid, "--script-mode"])

        for cmd in commands:
            try:
                logger.info("Trying tunnel: %s", " ".join(cmd))
                self._process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                success = await self._parse_tunnel_output()
                if success:
                    self.status = "connected"
                    logger.info("Tunnel established: %s:%d", self._rsd_address, self._rsd_port)
                    return True

                await self._kill_process()

            except Exception:
                logger.exception("Tunnel command failed: %s", " ".join(cmd))
                await self._kill_process()

        self.status = "error"
        return False

    async def _parse_tunnel_output(self) -> bool:
        """Parse tunnel subprocess output for RSD address and port.

        --script-mode outputs: HOST PORT (space-separated on one line)
        Normal mode outputs: RSD Address: <addr> / RSD Port: <port>
        """
        if not self._process or not self._process.stdout:
            return False

        try:
            for _ in range(60):  # 60 * 0.5s = 30s timeout
                try:
                    chunk = await asyncio.wait_for(
                        self._process.stdout.readline(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    if self._process.returncode is not None:
                        if self._process.stderr:
                            err = await self._process.stderr.read()
                            logger.error("Tunnel process died: %s", err.decode(errors="replace"))
                        return False
                    continue

                if not chunk:
                    break

                line = chunk.decode(errors="replace").strip()
                if not line:
                    continue

                logger.debug("Tunnel output: %s", line)

                # --script-mode: single line "HOST PORT"
                parts = line.split()
                if len(parts) == 2:
                    try:
                        port = int(parts[1])
                        self._rsd_address = parts[0]
                        self._rsd_port = port
                        return True
                    except ValueError:
                        pass

                # Normal mode: "RSD Address: fd00::1"
                addr_match = re.search(r"RSD Address:\s*(\S+)", line)
                if addr_match:
                    self._rsd_address = addr_match.group(1)

                port_match = re.search(r"RSD Port:\s*(\d+)", line)
                if port_match:
                    self._rsd_port = int(port_match.group(1))

                # If we have both from normal mode lines
                if self._rsd_address and self._rsd_port:
                    return True

            return False

        except Exception:
            logger.exception("Error parsing tunnel output")
            return False

    async def get_service_provider(self):
        """Return a RemoteServiceDiscoveryService connected through the tunnel."""
        if self.status != "connected" or not self._rsd_address or not self._rsd_port:
            return None

        try:
            from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
            rsd = RemoteServiceDiscoveryService((self._rsd_address, self._rsd_port))
            await rsd.connect()
            self._service_provider = rsd
            return rsd
        except Exception:
            logger.exception("Failed to connect RSD service")
            return None

    async def stop(self) -> None:
        """Stop the tunnel subprocess."""
        await self._kill_process()
        if self._service_provider is not None:
            try:
                self._service_provider.close()
            except Exception:
                pass
            self._service_provider = None
        self._rsd_address = None
        self._rsd_port = None
        self.status = "disconnected"

    async def _kill_process(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
            self._process = None
