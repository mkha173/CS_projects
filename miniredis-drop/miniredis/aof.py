"""Append-only file persistence.

Every write command is appended (as the original RESP bytes the client
sent) to a log file. On startup we replay the log to rebuild state. This
mirrors Redis's `appendonly yes` mode at its simplest setting.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional

from . import resp


class AOFLog:
    def __init__(self, path: Optional[Path]) -> None:
        self.path = Path(path) if path else None
        self._fh = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.path, "ab", buffering=0)

    def append(self, raw_command: bytes) -> None:
        if self._fh is None:
            return
        self._fh.write(raw_command)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def replay(self, apply_command: Callable[[str, List[bytes]], None]) -> int:
        """Read the log and feed each command to `apply_command`."""
        if self.path is None or not self.path.exists():
            return 0
        data = self.path.read_bytes()
        count = 0
        offset = 0
        while offset < len(data):
            try:
                value, offset = resp.parse(data, offset)
            except resp.IncompleteData:
                break  # truncated tail - safe to ignore
            if not isinstance(value, list) or not value:
                continue
            name = value[0]
            if isinstance(name, bytes):
                name_str = name.decode("utf-8", errors="replace")
            else:
                name_str = str(name)
            args = [a for a in value[1:] if isinstance(a, (bytes, bytearray))]
            apply_command(name_str, args)
            count += 1
        return count
