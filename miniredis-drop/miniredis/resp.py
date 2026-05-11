"""RESP (REdis Serialization Protocol) parser and encoder.

Supports the five RESP2 types:
    +<string>\r\n          simple string
    -<error>\r\n           error
    :<int>\r\n             integer
    $<len>\r\n<data>\r\n   bulk string ($-1\r\n = nil)
    *<len>\r\n<items>      array      (*-1\r\n  = nil)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union


# Sentinel types returned by the parser/encoder
class _Nil:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return "NIL"


NIL = _Nil()


@dataclass(frozen=True)
class SimpleString:
    value: str


@dataclass(frozen=True)
class Error:
    value: str


# A parsed RESP value can be any of the following
RespValue = Union[SimpleString, Error, int, bytes, list, _Nil, None]


class ProtocolError(ValueError):
    """Raised when bytes can't be parsed as RESP."""


class IncompleteData(Exception):
    """Raised when more bytes are needed to finish a parse."""


# ---------------------------------------------------------------------------
# Decoder
# ---------------------------------------------------------------------------

def parse(buf: bytes, offset: int = 0) -> Tuple[RespValue, int]:
    """Parse a single RESP value from `buf` starting at `offset`.

    Returns (value, new_offset). Raises IncompleteData if more bytes are
    required, ProtocolError if the bytes are malformed.
    """
    if offset >= len(buf):
        raise IncompleteData()

    marker = buf[offset:offset + 1]
    if marker == b"+":
        line, end = _read_line(buf, offset + 1)
        return SimpleString(line.decode("utf-8", errors="replace")), end
    if marker == b"-":
        line, end = _read_line(buf, offset + 1)
        return Error(line.decode("utf-8", errors="replace")), end
    if marker == b":":
        line, end = _read_line(buf, offset + 1)
        try:
            return int(line), end
        except ValueError as exc:
            raise ProtocolError(f"bad integer: {line!r}") from exc
    if marker == b"$":
        line, end = _read_line(buf, offset + 1)
        try:
            length = int(line)
        except ValueError as exc:
            raise ProtocolError(f"bad bulk length: {line!r}") from exc
        if length == -1:
            return NIL, end
        if length < 0:
            raise ProtocolError("negative bulk length")
        if end + length + 2 > len(buf):
            raise IncompleteData()
        data = buf[end:end + length]
        if buf[end + length:end + length + 2] != b"\r\n":
            raise ProtocolError("missing CRLF after bulk")
        return data, end + length + 2
    if marker == b"*":
        line, end = _read_line(buf, offset + 1)
        try:
            length = int(line)
        except ValueError as exc:
            raise ProtocolError(f"bad array length: {line!r}") from exc
        if length == -1:
            return NIL, end
        if length < 0:
            raise ProtocolError("negative array length")
        items: List[RespValue] = []
        for _ in range(length):
            value, end = parse(buf, end)
            items.append(value)
        return items, end
    # Inline commands (telnet style) - convenience for `redis-cli` and humans.
    if marker not in (b"", b"\r", b"\n"):
        line, end = _read_line(buf, offset)
        parts = line.split()
        return [p for p in parts], end
    raise ProtocolError(f"unknown marker: {marker!r}")


def _read_line(buf: bytes, offset: int) -> Tuple[bytes, int]:
    idx = buf.find(b"\r\n", offset)
    if idx == -1:
        raise IncompleteData()
    return buf[offset:idx], idx + 2


# ---------------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------------

def encode(value: RespValue) -> bytes:
    """Serialise a Python value to RESP bytes."""
    if value is None or isinstance(value, _Nil):
        return b"$-1\r\n"
    if isinstance(value, SimpleString):
        return b"+" + value.value.encode("utf-8") + b"\r\n"
    if isinstance(value, Error):
        return b"-" + value.value.encode("utf-8") + b"\r\n"
    if isinstance(value, bool):
        # bool is a subclass of int - encode as int (0/1)
        return b":" + (b"1" if value else b"0") + b"\r\n"
    if isinstance(value, int):
        return b":" + str(value).encode() + b"\r\n"
    if isinstance(value, (bytes, bytearray)):
        return b"$" + str(len(value)).encode() + b"\r\n" + bytes(value) + b"\r\n"
    if isinstance(value, str):
        data = value.encode("utf-8")
        return b"$" + str(len(data)).encode() + b"\r\n" + data + b"\r\n"
    if isinstance(value, (list, tuple)):
        out = b"*" + str(len(value)).encode() + b"\r\n"
        for item in value:
            out += encode(item)
        return out
    raise TypeError(f"can't encode {type(value).__name__}")


def encode_command(*parts: Union[str, bytes, int]) -> bytes:
    """Build a command array - useful for tests and clients."""
    pieces: List[bytes] = []
    for p in parts:
        if isinstance(p, bytes):
            pieces.append(p)
        elif isinstance(p, str):
            pieces.append(p.encode("utf-8"))
        else:
            pieces.append(str(p).encode("utf-8"))
    return encode(pieces)
