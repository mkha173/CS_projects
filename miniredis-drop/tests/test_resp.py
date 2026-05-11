"""Unit tests for the RESP codec."""

import pytest

from miniredis import resp


def test_parse_simple_string():
    val, off = resp.parse(b"+OK\r\n")
    assert val == resp.SimpleString("OK")
    assert off == 5


def test_parse_error():
    val, off = resp.parse(b"-ERR boom\r\n")
    assert val == resp.Error("ERR boom")
    assert off == 11


def test_parse_integer():
    val, off = resp.parse(b":42\r\n")
    assert val == 42
    assert off == 5


def test_parse_bulk_string():
    val, off = resp.parse(b"$5\r\nhello\r\n")
    assert val == b"hello"
    assert off == 11


def test_parse_nil_bulk():
    val, off = resp.parse(b"$-1\r\n")
    assert val is resp.NIL
    assert off == 5


def test_parse_array():
    raw = b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n"
    val, off = resp.parse(raw)
    assert val == [b"GET", b"foo"]
    assert off == len(raw)


def test_incomplete_raises():
    with pytest.raises(resp.IncompleteData):
        resp.parse(b"*2\r\n$3\r\nGET\r\n$3\r\nfo")


def test_encode_roundtrip_int():
    assert resp.encode(42) == b":42\r\n"


def test_encode_bytes():
    assert resp.encode(b"abc") == b"$3\r\nabc\r\n"


def test_encode_nil():
    assert resp.encode(None) == b"$-1\r\n"
    assert resp.encode(resp.NIL) == b"$-1\r\n"


def test_encode_array():
    assert resp.encode([b"a", b"b"]) == b"*2\r\n$1\r\na\r\n$1\r\nb\r\n"


def test_encode_command_helper():
    assert resp.encode_command("SET", "k", 7) == b"*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$1\r\n7\r\n"


def test_inline_command():
    val, off = resp.parse(b"PING\r\n")
    assert val == [b"PING"]
    assert off == 6


def test_streaming_partial_then_full():
    raw = b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n"
    # First half is incomplete...
    with pytest.raises(resp.IncompleteData):
        resp.parse(raw[:10])
    # Full buffer parses fine.
    val, off = resp.parse(raw)
    assert val == [b"GET", b"foo"]
