"""In-memory storage with active+passive TTL expiration.

The store is intentionally simple - one dict, one lock - but it supports
the data shapes used by the implemented commands: strings (bytes), lists
(deque), hashes (dict), and sets (set). Mixing types on one key is rejected
with WRONGTYPE, matching real Redis.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


class WrongType(Exception):
    """Raised when a command targets a key with an incompatible type."""


@dataclass
class _Entry:
    value: Any
    # Absolute monotonic-clock expiry. None means no TTL.
    expires_at: Optional[float] = None

    def is_expired(self, now: float) -> bool:
        return self.expires_at is not None and self.expires_at <= now


class Storage:
    """Thread-safe key/value store with TTL support."""

    def __init__(self) -> None:
        self._data: Dict[bytes, _Entry] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _get_entry(self, key: bytes, *, expect_type: Optional[type] = None) -> Optional[_Entry]:
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.is_expired(time.monotonic()):
            self._data.pop(key, None)
            return None
        if expect_type is not None and not isinstance(entry.value, expect_type):
            raise WrongType("WRONGTYPE Operation against a key holding the wrong kind of value")
        return entry

    def _put(self, key: bytes, value: Any, *, expires_at: Optional[float] = None) -> None:
        self._data[key] = _Entry(value=value, expires_at=expires_at)

    # ------------------------------------------------------------------
    # Generic key ops
    # ------------------------------------------------------------------
    def exists(self, keys: Iterable[bytes]) -> int:
        with self._lock:
            return sum(1 for k in keys if self._get_entry(k) is not None)

    def delete(self, keys: Iterable[bytes]) -> int:
        with self._lock:
            removed = 0
            now = time.monotonic()
            for k in keys:
                entry = self._data.get(k)
                if entry is None:
                    continue
                if entry.is_expired(now):
                    self._data.pop(k, None)
                    continue
                self._data.pop(k, None)
                removed += 1
            return removed

    def keys(self) -> List[bytes]:
        with self._lock:
            now = time.monotonic()
            live: List[bytes] = []
            stale: List[bytes] = []
            for k, entry in self._data.items():
                if entry.is_expired(now):
                    stale.append(k)
                else:
                    live.append(k)
            for k in stale:
                self._data.pop(k, None)
            return live

    def expire(self, key: bytes, seconds: float) -> bool:
        with self._lock:
            entry = self._get_entry(key)
            if entry is None:
                return False
            entry.expires_at = time.monotonic() + seconds
            return True

    def persist(self, key: bytes) -> bool:
        with self._lock:
            entry = self._get_entry(key)
            if entry is None or entry.expires_at is None:
                return False
            entry.expires_at = None
            return True

    def ttl(self, key: bytes) -> int:
        """Return remaining TTL in seconds. -2 if missing, -1 if no TTL."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return -2
            now = time.monotonic()
            if entry.is_expired(now):
                self._data.pop(key, None)
                return -2
            if entry.expires_at is None:
                return -1
            return max(0, int(entry.expires_at - now))

    def type_of(self, key: bytes) -> str:
        with self._lock:
            entry = self._get_entry(key)
            if entry is None:
                return "none"
            v = entry.value
            if isinstance(v, bytes):
                return "string"
            if isinstance(v, deque):
                return "list"
            if isinstance(v, dict):
                return "hash"
            if isinstance(v, set):
                return "set"
            return "unknown"

    def flushall(self) -> None:
        with self._lock:
            self._data.clear()

    def size(self) -> int:
        return len(self.keys())

    # ------------------------------------------------------------------
    # String ops
    # ------------------------------------------------------------------
    def set(
        self,
        key: bytes,
        value: bytes,
        *,
        ex_seconds: Optional[float] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        with self._lock:
            existing = self._get_entry(key)
            if nx and existing is not None:
                return False
            if xx and existing is None:
                return False
            expires_at = time.monotonic() + ex_seconds if ex_seconds is not None else None
            self._put(key, value, expires_at=expires_at)
            return True

    def get(self, key: bytes) -> Optional[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=bytes)
            return entry.value if entry else None

    def incrby(self, key: bytes, delta: int) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=bytes)
            current = 0
            expires_at = None
            if entry is not None:
                try:
                    current = int(entry.value)
                except ValueError as exc:
                    raise WrongType("ERR value is not an integer or out of range") from exc
                expires_at = entry.expires_at
            new = current + delta
            self._put(key, str(new).encode(), expires_at=expires_at)
            return new

    def append(self, key: bytes, value: bytes) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=bytes)
            if entry is None:
                self._put(key, value)
                return len(value)
            entry.value = entry.value + value
            return len(entry.value)

    def strlen(self, key: bytes) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=bytes)
            return len(entry.value) if entry else 0

    # ------------------------------------------------------------------
    # List ops
    # ------------------------------------------------------------------
    def _ensure_list(self, key: bytes) -> deque:
        entry = self._get_entry(key, expect_type=deque)
        if entry is None:
            dq: deque = deque()
            self._put(key, dq)
            return dq
        return entry.value

    def lpush(self, key: bytes, values: List[bytes]) -> int:
        with self._lock:
            dq = self._ensure_list(key)
            for v in values:
                dq.appendleft(v)
            return len(dq)

    def rpush(self, key: bytes, values: List[bytes]) -> int:
        with self._lock:
            dq = self._ensure_list(key)
            dq.extend(values)
            return len(dq)

    def lpop(self, key: bytes) -> Optional[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=deque)
            if entry is None or not entry.value:
                return None
            v = entry.value.popleft()
            if not entry.value:
                self._data.pop(key, None)
            return v

    def rpop(self, key: bytes) -> Optional[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=deque)
            if entry is None or not entry.value:
                return None
            v = entry.value.pop()
            if not entry.value:
                self._data.pop(key, None)
            return v

    def llen(self, key: bytes) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=deque)
            return len(entry.value) if entry else 0

    def lrange(self, key: bytes, start: int, stop: int) -> List[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=deque)
            if entry is None:
                return []
            items = list(entry.value)
            n = len(items)
            if start < 0:
                start = max(0, n + start)
            if stop < 0:
                stop = n + stop
            stop = min(stop, n - 1)
            if start > stop:
                return []
            return items[start:stop + 1]

    # ------------------------------------------------------------------
    # Hash ops
    # ------------------------------------------------------------------
    def _ensure_hash(self, key: bytes) -> Dict[bytes, bytes]:
        entry = self._get_entry(key, expect_type=dict)
        if entry is None:
            h: Dict[bytes, bytes] = {}
            self._put(key, h)
            return h
        return entry.value

    def hset(self, key: bytes, pairs: List[Tuple[bytes, bytes]]) -> int:
        with self._lock:
            h = self._ensure_hash(key)
            added = 0
            for f, v in pairs:
                if f not in h:
                    added += 1
                h[f] = v
            return added

    def hget(self, key: bytes, field: bytes) -> Optional[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=dict)
            if entry is None:
                return None
            return entry.value.get(field)

    def hdel(self, key: bytes, fields: List[bytes]) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=dict)
            if entry is None:
                return 0
            removed = 0
            for f in fields:
                if f in entry.value:
                    del entry.value[f]
                    removed += 1
            if not entry.value:
                self._data.pop(key, None)
            return removed

    def hgetall(self, key: bytes) -> List[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=dict)
            if entry is None:
                return []
            out: List[bytes] = []
            for f, v in entry.value.items():
                out.append(f)
                out.append(v)
            return out

    def hkeys(self, key: bytes) -> List[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=dict)
            return list(entry.value.keys()) if entry else []

    def hlen(self, key: bytes) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=dict)
            return len(entry.value) if entry else 0

    # ------------------------------------------------------------------
    # Set ops
    # ------------------------------------------------------------------
    def _ensure_set(self, key: bytes) -> Set[bytes]:
        entry = self._get_entry(key, expect_type=set)
        if entry is None:
            s: Set[bytes] = set()
            self._put(key, s)
            return s
        return entry.value

    def sadd(self, key: bytes, members: List[bytes]) -> int:
        with self._lock:
            s = self._ensure_set(key)
            added = 0
            for m in members:
                if m not in s:
                    s.add(m)
                    added += 1
            return added

    def srem(self, key: bytes, members: List[bytes]) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=set)
            if entry is None:
                return 0
            removed = 0
            for m in members:
                if m in entry.value:
                    entry.value.discard(m)
                    removed += 1
            if not entry.value:
                self._data.pop(key, None)
            return removed

    def smembers(self, key: bytes) -> List[bytes]:
        with self._lock:
            entry = self._get_entry(key, expect_type=set)
            return list(entry.value) if entry else []

    def scard(self, key: bytes) -> int:
        with self._lock:
            entry = self._get_entry(key, expect_type=set)
            return len(entry.value) if entry else 0

    def sismember(self, key: bytes, member: bytes) -> bool:
        with self._lock:
            entry = self._get_entry(key, expect_type=set)
            return entry is not None and member in entry.value

    # ------------------------------------------------------------------
    # Active expiration sweep (called by server periodically)
    # ------------------------------------------------------------------
    def sweep_expired(self, sample: int = 64) -> int:
        with self._lock:
            now = time.monotonic()
            stale = [k for i, (k, e) in enumerate(self._data.items())
                     if i < sample and e.is_expired(now)]
            for k in stale:
                self._data.pop(k, None)
            return len(stale)

    # ------------------------------------------------------------------
    # Snapshot for AOF rebuild / tests
    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[bytes, Tuple[Any, Optional[float]]]:
        """Return a shallow copy of live entries, including absolute TTLs."""
        with self._lock:
            now = time.monotonic()
            out: Dict[bytes, Tuple[Any, Optional[float]]] = {}
            for k, e in self._data.items():
                if e.is_expired(now):
                    continue
                ttl_remaining = (e.expires_at - now) if e.expires_at else None
                out[k] = (e.value, ttl_remaining)
            return out
