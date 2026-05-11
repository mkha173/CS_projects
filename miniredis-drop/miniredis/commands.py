"""Command dispatch table.

Each handler takes (server, args: List[bytes]) and returns a RESP-encodable
value. Argument validation is done per-handler so we can report Redis-style
error strings.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from .resp import Error, SimpleString, NIL
from .storage import WrongType


def _wrong_args(cmd: str) -> Error:
    return Error(f"ERR wrong number of arguments for '{cmd.lower()}' command")


def _as_int(b: bytes, *, what: str = "value") -> int:
    try:
        return int(b)
    except ValueError as exc:
        raise WrongType(f"ERR {what} is not an integer or out of range") from exc


# ---------------------------------------------------------------------------
# Generic / connection
# ---------------------------------------------------------------------------

def cmd_ping(server, args):
    if len(args) == 0:
        return SimpleString("PONG")
    if len(args) == 1:
        return args[0]
    return _wrong_args("ping")


def cmd_echo(server, args):
    if len(args) != 1:
        return _wrong_args("echo")
    return args[0]


def cmd_command(server, args):
    # Minimal stub - clients like redis-cli send COMMAND DOCS / COUNT at startup.
    return []


def cmd_dbsize(server, args):
    if args:
        return _wrong_args("dbsize")
    return server.storage.size()


def cmd_flushall(server, args):
    server.storage.flushall()
    return SimpleString("OK")


def cmd_flushdb(server, args):
    server.storage.flushall()
    return SimpleString("OK")


def cmd_keys(server, args):
    # Real Redis takes a glob; we just return all live keys.
    return server.storage.keys()


def cmd_type(server, args):
    if len(args) != 1:
        return _wrong_args("type")
    return SimpleString(server.storage.type_of(args[0]))


def cmd_exists(server, args):
    if not args:
        return _wrong_args("exists")
    return server.storage.exists(args)


def cmd_del(server, args):
    if not args:
        return _wrong_args("del")
    return server.storage.delete(args)


def cmd_expire(server, args):
    if len(args) != 2:
        return _wrong_args("expire")
    seconds = _as_int(args[1])
    return 1 if server.storage.expire(args[0], seconds) else 0


def cmd_persist(server, args):
    if len(args) != 1:
        return _wrong_args("persist")
    return 1 if server.storage.persist(args[0]) else 0


def cmd_ttl(server, args):
    if len(args) != 1:
        return _wrong_args("ttl")
    return server.storage.ttl(args[0])


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

def cmd_set(server, args):
    if len(args) < 2:
        return _wrong_args("set")
    key, value = args[0], args[1]
    ex_seconds = None
    nx = False
    xx = False
    i = 2
    while i < len(args):
        opt = args[i].upper()
        if opt == b"EX" and i + 1 < len(args):
            ex_seconds = _as_int(args[i + 1])
            i += 2
        elif opt == b"PX" and i + 1 < len(args):
            ex_seconds = _as_int(args[i + 1]) / 1000.0
            i += 2
        elif opt == b"NX":
            nx = True
            i += 1
        elif opt == b"XX":
            xx = True
            i += 1
        else:
            return Error("ERR syntax error")
    ok = server.storage.set(key, value, ex_seconds=ex_seconds, nx=nx, xx=xx)
    return SimpleString("OK") if ok else NIL


def cmd_get(server, args):
    if len(args) != 1:
        return _wrong_args("get")
    v = server.storage.get(args[0])
    return v if v is not None else NIL


def cmd_incr(server, args):
    if len(args) != 1:
        return _wrong_args("incr")
    return server.storage.incrby(args[0], 1)


def cmd_decr(server, args):
    if len(args) != 1:
        return _wrong_args("decr")
    return server.storage.incrby(args[0], -1)


def cmd_incrby(server, args):
    if len(args) != 2:
        return _wrong_args("incrby")
    return server.storage.incrby(args[0], _as_int(args[1]))


def cmd_decrby(server, args):
    if len(args) != 2:
        return _wrong_args("decrby")
    return server.storage.incrby(args[0], -_as_int(args[1]))


def cmd_append(server, args):
    if len(args) != 2:
        return _wrong_args("append")
    return server.storage.append(args[0], args[1])


def cmd_strlen(server, args):
    if len(args) != 1:
        return _wrong_args("strlen")
    return server.storage.strlen(args[0])


def cmd_mset(server, args):
    if len(args) < 2 or len(args) % 2 != 0:
        return _wrong_args("mset")
    for i in range(0, len(args), 2):
        server.storage.set(args[i], args[i + 1])
    return SimpleString("OK")


def cmd_mget(server, args):
    if not args:
        return _wrong_args("mget")
    out = []
    for k in args:
        v = server.storage.get(k)
        out.append(v if v is not None else NIL)
    return out


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

def cmd_lpush(server, args):
    if len(args) < 2:
        return _wrong_args("lpush")
    return server.storage.lpush(args[0], list(args[1:]))


def cmd_rpush(server, args):
    if len(args) < 2:
        return _wrong_args("rpush")
    return server.storage.rpush(args[0], list(args[1:]))


def cmd_lpop(server, args):
    if len(args) != 1:
        return _wrong_args("lpop")
    v = server.storage.lpop(args[0])
    return v if v is not None else NIL


def cmd_rpop(server, args):
    if len(args) != 1:
        return _wrong_args("rpop")
    v = server.storage.rpop(args[0])
    return v if v is not None else NIL


def cmd_llen(server, args):
    if len(args) != 1:
        return _wrong_args("llen")
    return server.storage.llen(args[0])


def cmd_lrange(server, args):
    if len(args) != 3:
        return _wrong_args("lrange")
    return server.storage.lrange(args[0], _as_int(args[1]), _as_int(args[2]))


# ---------------------------------------------------------------------------
# Hashes
# ---------------------------------------------------------------------------

def cmd_hset(server, args):
    if len(args) < 3 or (len(args) - 1) % 2 != 0:
        return _wrong_args("hset")
    pairs = [(args[i], args[i + 1]) for i in range(1, len(args), 2)]
    return server.storage.hset(args[0], pairs)


def cmd_hget(server, args):
    if len(args) != 2:
        return _wrong_args("hget")
    v = server.storage.hget(args[0], args[1])
    return v if v is not None else NIL


def cmd_hdel(server, args):
    if len(args) < 2:
        return _wrong_args("hdel")
    return server.storage.hdel(args[0], list(args[1:]))


def cmd_hgetall(server, args):
    if len(args) != 1:
        return _wrong_args("hgetall")
    return server.storage.hgetall(args[0])


def cmd_hkeys(server, args):
    if len(args) != 1:
        return _wrong_args("hkeys")
    return server.storage.hkeys(args[0])


def cmd_hlen(server, args):
    if len(args) != 1:
        return _wrong_args("hlen")
    return server.storage.hlen(args[0])


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------

def cmd_sadd(server, args):
    if len(args) < 2:
        return _wrong_args("sadd")
    return server.storage.sadd(args[0], list(args[1:]))


def cmd_srem(server, args):
    if len(args) < 2:
        return _wrong_args("srem")
    return server.storage.srem(args[0], list(args[1:]))


def cmd_smembers(server, args):
    if len(args) != 1:
        return _wrong_args("smembers")
    return server.storage.smembers(args[0])


def cmd_scard(server, args):
    if len(args) != 1:
        return _wrong_args("scard")
    return server.storage.scard(args[0])


def cmd_sismember(server, args):
    if len(args) != 2:
        return _wrong_args("sismember")
    return 1 if server.storage.sismember(args[0], args[1]) else 0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Commands that mutate state - the AOF logger persists these.
WRITE_COMMANDS = {
    "SET", "DEL", "EXPIRE", "PERSIST", "INCR", "DECR", "INCRBY", "DECRBY",
    "APPEND", "MSET", "LPUSH", "RPUSH", "LPOP", "RPOP",
    "HSET", "HDEL", "SADD", "SREM", "FLUSHALL", "FLUSHDB",
}

COMMANDS: Dict[str, Callable] = {
    "PING": cmd_ping,
    "ECHO": cmd_echo,
    "COMMAND": cmd_command,
    "DBSIZE": cmd_dbsize,
    "FLUSHALL": cmd_flushall,
    "FLUSHDB": cmd_flushdb,
    "KEYS": cmd_keys,
    "TYPE": cmd_type,
    "EXISTS": cmd_exists,
    "DEL": cmd_del,
    "EXPIRE": cmd_expire,
    "PERSIST": cmd_persist,
    "TTL": cmd_ttl,
    "SET": cmd_set,
    "GET": cmd_get,
    "INCR": cmd_incr,
    "DECR": cmd_decr,
    "INCRBY": cmd_incrby,
    "DECRBY": cmd_decrby,
    "APPEND": cmd_append,
    "STRLEN": cmd_strlen,
    "MSET": cmd_mset,
    "MGET": cmd_mget,
    "LPUSH": cmd_lpush,
    "RPUSH": cmd_rpush,
    "LPOP": cmd_lpop,
    "RPOP": cmd_rpop,
    "LLEN": cmd_llen,
    "LRANGE": cmd_lrange,
    "HSET": cmd_hset,
    "HGET": cmd_hget,
    "HDEL": cmd_hdel,
    "HGETALL": cmd_hgetall,
    "HKEYS": cmd_hkeys,
    "HLEN": cmd_hlen,
    "SADD": cmd_sadd,
    "SREM": cmd_srem,
    "SMEMBERS": cmd_smembers,
    "SCARD": cmd_scard,
    "SISMEMBER": cmd_sismember,
}


def dispatch(server, name: str, args: List[bytes]):
    handler = COMMANDS.get(name.upper())
    if handler is None:
        return Error(f"ERR unknown command '{name}'")
    try:
        return handler(server, args)
    except WrongType as exc:
        return Error(str(exc))
    except ValueError as exc:
        return Error(f"ERR {exc}")
