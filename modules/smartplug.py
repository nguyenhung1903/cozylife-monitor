import json
import socket
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class DPID(IntEnum):
    """Data point IDs reported by the CozyLife smart plug."""
    POWER_STATUS = 1  # Relay state: 1 = on, 0 = off
    POWER_W = 28      # Instantaneous power (raw value, see note in read())


@dataclass
class PlugReading:
    """Parsed result of a single plug query."""
    is_on: Optional[bool]       # None if the plug did not report the relay state
    power_w: Optional[float]    # None if the plug has no power metering
    raw: dict                   # Full DPID -> value payload for debugging


class SmartPlug:
    """Minimal local TCP client for a CozyLife smart plug (default port 5555)."""

    def __init__(self, ip: str, port: int = 5555, timeout: float = 5.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        
        print(f"Initialize: {ip} - {port}")

    def _query(self, attr: list) -> dict:
        """Send a state query (cmd 2) and return the decoded JSON response."""
        payload = {
            "cmd": 2,                          # 2 = query device state
            "pv": 0,
            "sn": str(int(time.time() * 1000)),  # Unique serial number per request
            "msg": {"attr": attr, "data": {}},   # attr [0] = request all DPIDs
        }
        with socket.create_connection((self.ip, self.port), timeout=self.timeout) as s:
            # The protocol is newline-delimited JSON (terminated by \r\n)
            s.sendall((json.dumps(payload) + "\r\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:  # Connection closed by the plug
                    break
                buf += chunk

        # The plug may send several lines; use the last valid JSON one
        for line in reversed(buf.decode().strip().splitlines()):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        raise ValueError("No valid JSON response received")

    def read(self) -> PlugReading:
        """Query the plug and return its relay state and power usage."""
        data = self._query([0]).get("msg", {}).get("data", {})
        
        # DPID keys are strings in the JSON payload
        status = data.get(str(DPID.POWER_STATUS))
        power = data.get(str(DPID.POWER_W))

        return PlugReading(
            is_on=None if status is None else bool(status),
            power_w=power,
            raw=data,
        )


if __name__ == "__main__":
    plug = SmartPlug("192.168.1.100")
    try:
        r = plug.read()
    except (OSError, ValueError) as e:
        print(f"Error: {e}")
    else:
        print(f"State: {'On' if r.is_on else 'Off'}")
        print(f"Power: {r.power_w} W")
        print(f"Raw data: {r.raw}")