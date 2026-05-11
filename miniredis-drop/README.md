# miniredis

A minimal, single-binary key/value server that speaks the Redis RESP2 protocol. You can point `redis-cli` (or any Redis client library) at it and it will respond.

## What it does

- TCP server built on `asyncio` that accepts many concurrent clients
- Full RESP2 codec (simple strings, errors, integers, bulk strings, arrays, plus inline commands for telnet-style debugging)
- Data types: strings, lists, hashes, sets
- Active and passive TTL expiration
- Append-only-file (AOF) persistence with replay on startup
- ~40 commands implemented: `SET / GET / DEL / EXISTS / EXPIRE / PERSIST / TTL / TYPE / KEYS / DBSIZE / INCR / DECR / INCRBY / DECRBY / APPEND / STRLEN / MSET / MGET / LPUSH / RPUSH / LPOP / RPOP / LLEN / LRANGE / HSET / HGET / HDEL / HGETALL / HKEYS / HLEN / SADD / SREM / SMEMBERS / SCARD / SISMEMBER / PING / ECHO / FLUSHALL / FLUSHDB`

The whole thing is roughly 900 lines of Python with no third-party runtime dependencies.

## Run it

```bash
python -m miniredis --port 6380 --aof ./data.aof
```

Then in another terminal:

```bash
redis-cli -p 6380
127.0.0.1:6380> SET hello world
OK
127.0.0.1:6380> GET hello
"world"
127.0.0.1:6380> RPUSH names alice bob charlie
(integer) 3
127.0.0.1:6380> LRANGE names 0 -1
1) "alice"
2) "bob"
3) "charlie"
127.0.0.1:6380> SET token abc EX 5
OK
127.0.0.1:6380> TTL token
(integer) 5
```

Kill the server and start it again with the same `--aof` path; your data comes back.

## Test it

```bash
pip install pytest
pytest -v
```

The suite covers the RESP codec, the storage engine (with TTL, WRONGTYPE, and edge cases), and end-to-end tests that boot the server, push concurrent traffic from multiple threads, and verify AOF replay across restarts.

## Layout

```
miniredis/
  resp.py        # RESP2 parser + encoder
  storage.py     # in-memory store with TTL, types, locking
  commands.py    # command handlers + dispatch table
  aof.py         # append-only log + replay
  server.py      # asyncio TCP server, CLI entry point
tests/
  test_resp.py
  test_storage.py
  test_server.py
```

## What it deliberately doesn't do

- No cluster, no replication, no pub/sub
- No RDB snapshotting (AOF only)
- Single database (no `SELECT n`)
- `KEYS` returns everything; no glob matching

These are the natural next steps if you want to extend it.
