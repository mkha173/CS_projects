"""End-to-end tests that boot the server and talk RESP over a real socket."""

import asyncio
import socket
import threading
import time
from pathlib import Path

import pytest

from miniredis import resp
from miniredis.server import Server


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ServerHarness:
    """Spin up the asyncio server on a background thread for blocking tests."""

    def __init__(self, aof_path: Path | None = None):
        self.port = _free_port()
        self.aof_path = aof_path
        self.loop: asyncio.AbstractEventLoop | None = None
        self.server: Server | None = None
        self.thread: threading.Thread | None = None
        self._ready = threading.Event()

    def start(self) -> None:
        def runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.server = Server(port=self.port, aof_path=self.aof_path)
            self.loop.run_until_complete(self.server.start())
            self._ready.set()
            try:
                self.loop.run_until_complete(self.server.serve_forever())
            except asyncio.CancelledError:
                pass

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()
        self._ready.wait(timeout=5)
        # Tiny grace period so the listener fully accepts.
        time.sleep(0.05)

    def stop(self) -> None:
        if self.loop and self.server:
            async def _shutdown():
                await self.server.stop()
                # Cancel any still-running client handlers cleanly.
                tasks = [t for t in asyncio.all_tasks(self.loop)
                         if t is not asyncio.current_task()]
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.run_coroutine_threadsafe(_shutdown(), self.loop).result(timeout=5)
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=5)


@pytest.fixture
def server():
    h = ServerHarness()
    h.start()
    try:
        yield h
    finally:
        h.stop()


class Client:
    """Tiny blocking RESP client - good enough for tests."""

    def __init__(self, port: int):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.buf = b""

    def close(self):
        self.sock.close()

    def call(self, *parts):
        self.sock.sendall(resp.encode_command(*parts))
        return self._read_reply()

    def _read_reply(self):
        while True:
            try:
                value, offset = resp.parse(self.buf, 0)
                self.buf = self.buf[offset:]
                return value
            except resp.IncompleteData:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise ConnectionError("server closed")
                self.buf += chunk


def test_ping(server):
    c = Client(server.port)
    assert c.call("PING") == resp.SimpleString("PONG")
    assert c.call("PING", "hello") == b"hello"


def test_set_get(server):
    c = Client(server.port)
    assert c.call("SET", "name", "alice") == resp.SimpleString("OK")
    assert c.call("GET", "name") == b"alice"
    assert c.call("GET", "missing") is resp.NIL


def test_incr_counter(server):
    c = Client(server.port)
    assert c.call("INCR", "n") == 1
    assert c.call("INCR", "n") == 2
    assert c.call("INCRBY", "n", "10") == 12
    assert c.call("DECR", "n") == 11


def test_expire(server):
    c = Client(server.port)
    c.call("SET", "k", "v")
    assert c.call("EXPIRE", "k", "10") == 1
    ttl = c.call("TTL", "k")
    assert 0 <= ttl <= 10


def test_lists(server):
    c = Client(server.port)
    assert c.call("RPUSH", "l", "a", "b", "c") == 3
    assert c.call("LRANGE", "l", "0", "-1") == [b"a", b"b", b"c"]
    assert c.call("LPOP", "l") == b"a"
    assert c.call("LLEN", "l") == 2


def test_hashes(server):
    c = Client(server.port)
    assert c.call("HSET", "h", "f1", "v1", "f2", "v2") == 2
    assert c.call("HGET", "h", "f1") == b"v1"
    assert c.call("HLEN", "h") == 2
    body = c.call("HGETALL", "h")
    assert sorted(body) == [b"f1", b"f2", b"v1", b"v2"]


def test_sets(server):
    c = Client(server.port)
    assert c.call("SADD", "s", "a", "b", "a") == 2
    assert c.call("SCARD", "s") == 2
    assert c.call("SISMEMBER", "s", "a") == 1


def test_wrong_type_error(server):
    c = Client(server.port)
    c.call("SET", "k", "v")
    reply = c.call("LPUSH", "k", "x")
    assert isinstance(reply, resp.Error)
    assert "WRONGTYPE" in reply.value


def test_unknown_command(server):
    c = Client(server.port)
    reply = c.call("NOPE")
    assert isinstance(reply, resp.Error)
    assert "unknown command" in reply.value


def test_concurrent_clients(server):
    # Two clients hammering INCR on the same key must observe a serialised total.
    n_per_client = 100
    errors = []

    def worker():
        try:
            c = Client(server.port)
            for _ in range(n_per_client):
                c.call("INCR", "counter")
            c.close()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    c = Client(server.port)
    assert c.call("GET", "counter") == str(4 * n_per_client).encode()


def test_aof_persistence(tmp_path):
    aof = tmp_path / "appendonly.aof"
    # First boot: write some data.
    h1 = ServerHarness(aof_path=aof)
    h1.start()
    try:
        c = Client(h1.port)
        c.call("SET", "name", "alice")
        c.call("RPUSH", "list", "x", "y", "z")
        c.call("INCR", "counter")
        c.call("INCR", "counter")
        c.close()
    finally:
        h1.stop()

    # Second boot: state should be restored from the AOF.
    h2 = ServerHarness(aof_path=aof)
    h2.start()
    try:
        c = Client(h2.port)
        assert c.call("GET", "name") == b"alice"
        assert c.call("LRANGE", "list", "0", "-1") == [b"x", b"y", b"z"]
        assert c.call("GET", "counter") == b"2"
    finally:
        h2.stop()
