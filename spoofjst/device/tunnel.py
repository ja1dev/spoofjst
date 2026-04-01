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

logger = logging.getLogger(__name__)


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

        Launches `pymobiledevice3 remote start-tunnel` as a subprocess
        and parses its output for the RSD address and port.
        """
        await self.stop()
        self.status = "connecting"

        try:
            # Try the lockdown start-tunnel first (works for iOS 17.4+)
            self._process = await asyncio.create_subprocess_exec(
                "python3", "-m", "pymobiledevice3",
                "remote", "start-tunnel",
                "--udid", udid,
                "--script-mode",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Read output to find the RSD address/port
            # pymobiledevice3 outputs JSON like: {"tunnel-address": "...", "tunnel-port": ...}
            success = await self._parse_tunnel_output()
            if success:
                self.status = "connected"
                logger.info("Tunnel established: %s:%d", self._rsd_address, self._rsd_port)
                return True

            # If that failed, try the alternative tunnel command
            await self._kill_process()
            self._process = await asyncio.create_subprocess_exec(
                "python3", "-m", "pymobiledevice3",
                "lockdown", "start-tunnel",
                "--udid", udid,
                "--script-mode",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            success = await self._parse_tunnel_output()
            if success:
                self.status = "connected"
                logger.info("Tunnel established (lockdown): %s:%d", self._rsd_address, self._rsd_port)
                return True

            self.status = "error"
            return False

        except Exception:
            logger.exception("Failed to start tunnel")
            self.status = "error"
            return False

    async def _parse_tunnel_output(self) -> bool:
        """Parse tunnel subprocess output for RSD address and port.

        Returns True if successfully parsed, False on timeout or failure.
        """
        if not self._process or not self._process.stdout:
            return False

        try:
            # Wait up to 30 seconds for the tunnel to establish
            output = b""
            for _ in range(60):  # 60 * 0.5s = 30s
                try:
                    chunk = await asyncio.wait_for(
                        self._process.stdout.readline(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    # Check if process died
                    if self._process.returncode is not None:
                        if self._process.stderr:
                            err = await self._process.stderr.read()
                            logger.error("Tunnel process died: %s", err.decode(errors="replace"))
                        return False
                    continue

                if not chunk:
                    break

                output += chunk
                line = chunk.decode(errors="replace").strip()
                logger.debug("Tunnel output: %s", line)

                # Try to parse JSON output from --script-mode
                try:
                    data = json.loads(line)
                    addr = data.get("tunnel-address") or data.get("address")
                    port = data.get("tunnel-port") or data.get("port")
                    if addr and port:
                        self._rsd_address = str(addr)
                        self._rsd_port = int(port)
                        return True
                except (json.JSONDecodeError, ValueError):
                    pass

                # Fallback: parse plain text output like "address: fd00::1 port: 12345"
                match = re.search(r"(?:address|addr)[:\s]+(\S+).*?(?:port)[:\s]+(\d+)", line, re.IGNORECASE)
                if match:
                    self._rsd_address = match.group(1)
                    self._rsd_port = int(match.group(2))
                    return True

            return False

        except Exception:
            logger.exception("Error parsing tunnel output")
            return False

    def get_service_provider(self):
        """Return a RemoteServiceDiscoveryService connected through the tunnel."""
        if self.status != "connected" or not self._rsd_address or not self._rsd_port:
            return None

        try:
            from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
            rsd = RemoteServiceDiscoveryService((self._rsd_address, self._rsd_port))
            rsd.connect()
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
