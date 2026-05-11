"""Unit tests for the in-memory storage engine."""

import time

import pytest

from miniredis.storage import Storage, WrongType


def test_set_and_get():
    s = Storage()
    s.set(b"k", b"v")
    assert s.get(b"k") == b"v"


def test_get_missing_returns_none():
    s = Storage()
    assert s.get(b"missing") is None


def test_ttl_expires():
    s = Storage()
    s.set(b"k", b"v", ex_seconds=0.05)
    assert s.get(b"k") == b"v"
    time.sleep(0.1)
    assert s.get(b"k") is None


def test_ttl_query():
    s = Storage()
    assert s.ttl(b"missing") == -2
    s.set(b"k", b"v")
    assert s.ttl(b"k") == -1
    s.set(b"k2", b"v", ex_seconds=10)
    assert 0 <= s.ttl(b"k2") <= 10


def test_persist_clears_ttl():
    s = Storage()
    s.set(b"k", b"v", ex_seconds=5)
    assert s.persist(b"k")
    assert s.ttl(b"k") == -1


def test_set_nx_xx():
    s = Storage()
    assert s.set(b"k", b"v", nx=True) is True
    assert s.set(b"k", b"v2", nx=True) is False
    assert s.get(b"k") == b"v"
    assert s.set(b"k", b"v3", xx=True) is True
    assert s.get(b"k") == b"v3"
    assert s.set(b"missing", b"v", xx=True) is False


def test_incrby_starts_at_zero():
    s = Storage()
    assert s.incrby(b"counter", 1) == 1
    assert s.incrby(b"counter", 4) == 5
    assert s.incrby(b"counter", -2) == 3


def test_incrby_rejects_non_int():
    s = Storage()
    s.set(b"k", b"not-a-number")
    with pytest.raises(WrongType):
        s.incrby(b"k", 1)


def test_lists_push_pop():
    s = Storage()
    assert s.rpush(b"l", [b"a", b"b", b"c"]) == 3
    assert s.lpush(b"l", [b"x"]) == 4
    assert s.lrange(b"l", 0, -1) == [b"x", b"a", b"b", b"c"]
    assert s.lpop(b"l") == b"x"
    assert s.rpop(b"l") == b"c"
    assert s.llen(b"l") == 2


def test_lrange_negative():
    s = Storage()
    s.rpush(b"l", [b"a", b"b", b"c", b"d"])
    assert s.lrange(b"l", -2, -1) == [b"c", b"d"]
    assert s.lrange(b"l", 1, 2) == [b"b", b"c"]


def test_hash_ops():
    s = Storage()
    assert s.hset(b"h", [(b"name", b"alice"), (b"age", b"30")]) == 2
    assert s.hset(b"h", [(b"name", b"bob")]) == 0  # overwrite
    assert s.hget(b"h", b"name") == b"bob"
    assert s.hlen(b"h") == 2
    assert sorted(s.hkeys(b"h")) == [b"age", b"name"]
    assert s.hdel(b"h", [b"age"]) == 1
    assert s.hlen(b"h") == 1


def test_set_ops():
    s = Storage()
    assert s.sadd(b"s", [b"a", b"b", b"a"]) == 2
    assert s.scard(b"s") == 2
    assert s.sismember(b"s", b"a") is True
    assert s.srem(b"s", [b"a"]) == 1
    assert s.scard(b"s") == 1


def test_wrong_type_detection():
    s = Storage()
    s.set(b"k", b"v")
    with pytest.raises(WrongType):
        s.lpush(b"k", [b"x"])
    with pytest.raises(WrongType):
        s.hset(b"k", [(b"f", b"v")])
    with pytest.raises(WrongType):
        s.sadd(b"k", [b"m"])


def test_delete_returns_count():
    s = Storage()
    s.set(b"a", b"1")
    s.set(b"b", b"2")
    assert s.delete([b"a", b"b", b"missing"]) == 2
    assert s.exists([b"a", b"b"]) == 0
