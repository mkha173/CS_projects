"""Asyncio TCP server speaking RESP2."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from pathlib import Path
from typing import List, Optional

from . import resp
from .aof import AOFLog
from .commands import COMMANDS, WRITE_COMMANDS, dispatch
from .storage import Storage


log = logging.getLogger("miniredis")


class Server:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6380,
        aof_path: Optional[Path] = None,
        sweep_interval: float = 1.0,
    ) -> None:
        self.host = host
        self.port = port
        self.storage = Storage()
        self.aof = AOFLog(aof_path)
        self.sweep_interval = sweep_interval
        self._server: Optional[asyncio.AbstractServer] = None
        self._sweep_task: Optional[asyncio.Task] = None
        self._connections = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        # Replay AOF first so state is restored before accepting clients.
        replayed = self.aof.replay(self._apply_replayed)
        if replayed:
            log.info("replayed %d commands from AOF", replayed)
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        addr = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        log.info("listening on %s", addr)
        self._sweep_task = asyncio.create_task(self._sweep_loop())

    async def serve_forever(self) -> None:
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            try:
                await self._sweep_task
            except asyncio.CancelledError:
                pass
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self.aof.close()

    # ------------------------------------------------------------------
    # Client handling
    # ------------------------------------------------------------------
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        self._connections += 1
        log.info("client connected: %s (open=%d)", peer, self._connections)
        buf = b""
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                buf += chunk
                # Drain any complete commands in the buffer.
                while True:
                    try:
                        value, new_offset = resp.parse(buf, 0)
                    except resp.IncompleteData:
                        break
                    except resp.ProtocolError as exc:
                        writer.write(resp.encode(resp.Error(f"ERR protocol error: {exc}")))
                        await writer.drain()
                        return
                    raw_command = buf[:new_offset]
                    buf = buf[new_offset:]
                    response = self._run_command(value, raw_command)
                    writer.write(resp.encode(response))
                    try:
                        await writer.drain()
                    except ConnectionError:
                        return
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            self._connections -= 1
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            log.info("client disconnected: %s (open=%d)", peer, self._connections)

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------
    def _run_command(self, value, raw_command: bytes):
        if not isinstance(value, list) or not value:
            return resp.Error("ERR malformed command")
        head = value[0]
        if isinstance(head, bytes):
            name = head.decode("utf-8", errors="replace")
        else:
            name = str(head)
        args: List[bytes] = []
        for a in value[1:]:
            if isinstance(a, (bytes, bytearray)):
                args.append(bytes(a))
            elif isinstance(a, int):
                args.append(str(a).encode())
            else:
                # SimpleString / Error - convert to bytes
                args.append(str(getattr(a, "value", a)).encode())
        result = dispatch(self, name, args)
        if name.upper() in WRITE_COMMANDS and not isinstance(result, resp.Error):
            self.aof.append(raw_command)
        return result

    def _apply_replayed(self, name: str, args: List[bytes]) -> None:
        # Direct dispatch, skip AOF write-back.
        dispatch(self, name, args)

    # ------------------------------------------------------------------
    # Background expiration sweep
    # ------------------------------------------------------------------
    async def _sweep_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.sweep_interval)
                self.storage.sweep_expired()
        except asyncio.CancelledError:
            return


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="miniredis - a RESP-compatible key/value server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=6380)
    p.add_argument("--aof", type=Path, default=None,
                   help="Path to the append-only log file. Omit for in-memory only.")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


async def _amain(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    server = Server(host=args.host, port=args.port, aof_path=args.aof)
    await server.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_stop():
        log.info("shutting down")
        stop_event.set()

    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                loop.add_signal_handler(getattr(signal, sig_name), _signal_stop)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler for SIGTERM
                pass

    serve_task = asyncio.create_task(server.serve_forever())
    stop_task = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {serve_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()
    await server.stop()
    return 0


def main(argv=None) -> int:
    try:
        return asyncio.run(_amain(argv))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
