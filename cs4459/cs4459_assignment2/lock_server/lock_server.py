"""
Lock Server — 

A FastAPI service that provides centralized mutual exclusion for the
ticket booking system. Workers must acquire the lock before booking seats.

Part 1: Implement /acquire, /release, /status, /health
Part 2: Add /heartbeat endpoint and background timeout monitoring
"""

import os
import logging
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel

from helpers import generate_token  # DO NOT MODIFY helpers.py

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 6000))

# Part 2: heartbeat timeout in seconds (4x the 500ms heartbeat interval)
HEARTBEAT_TIMEOUT = float(os.environ.get("HEARTBEAT_TIMEOUT", 2.0))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [lock-server] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class AcquireRequest(BaseModel):
    worker_id: str


class AcquireResponse(BaseModel):
    granted: bool
    token: str | None = None
    position: int | None = None


class ReleaseRequest(BaseModel):
    worker_id: str
    token: str


class ReleaseResponse(BaseModel):
    released: bool
    error: str | None = None


class HeartbeatRequest(BaseModel):
    worker_id: str
    token: str


class HeartbeatResponse(BaseModel):
    valid: bool
    error: str | None = None


class StatusResponse(BaseModel):
    holder: str | None = None
    queue: list[str] = []
    token: str | None = None


# ---------------------------------------------------------------------------
# Lock state
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()

# Current lock holder info
lock_holder: str | None = None          # worker_id
lock_token: str | None = None           # fencing token
lock_queue: deque = deque()             # FIFO queue of waiting worker_ids

# Part 2: heartbeat tracking
last_heartbeat: float = 0.0             # time.monotonic() of last heartbeat


# ---------------------------------------------------------------------------
# Part 2: Background timeout monitor
# ---------------------------------------------------------------------------

def _timeout_monitor():
    """Background thread: revoke lock if holder misses heartbeats."""
    while True:
        time.sleep(0.5)
        with _state_lock:
            if lock_holder is not None:
                elapsed = time.monotonic() - last_heartbeat
                if elapsed > HEARTBEAT_TIMEOUT:
                    logger.warning(
                        "Heartbeat timeout for %s (elapsed=%.1fs). Revoking lock.",
                        lock_holder, elapsed,
                    )
                    _grant_next()


def _grant_next():
    """Grant the lock to the next worker in the queue (must hold _state_lock)."""
    global lock_holder, lock_token, last_heartbeat
    if lock_queue:
        next_worker = lock_queue.popleft()
        lock_holder = next_worker
        lock_token = generate_token(next_worker)
        last_heartbeat = time.monotonic()
        logger.info("Lock granted to %s (token=%s)", lock_holder, lock_token)
    else:
        lock_holder = None
        lock_token = None
        last_heartbeat = 0.0


# ---------------------------------------------------------------------------
# Application lifespan — start background monitor thread here
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor = threading.Thread(target=_timeout_monitor, daemon=True, name="heartbeat-monitor")
    monitor.start()
    logger.info("Heartbeat timeout monitor started (timeout=%.1fs).", HEARTBEAT_TIMEOUT)
    yield


app = FastAPI(title="Lock Server", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Part 1 Endpoints
# ---------------------------------------------------------------------------

@app.post("/acquire", response_model=AcquireResponse)
def acquire_lock(request: AcquireRequest):
    """
    Acquire the distributed lock.

    - If the lock is free, grant it immediately and return granted=True with a token.
    - If the lock is held, enqueue the worker and return granted=False with queue position.
    """
    global lock_holder, lock_token, last_heartbeat

    with _state_lock:
        if lock_holder is None:
            # Grant immediately
            lock_holder = request.worker_id
            lock_token = generate_token(request.worker_id)
            last_heartbeat = time.monotonic()
            logger.info("Lock granted to %s (token=%s)", lock_holder, lock_token)
            return AcquireResponse(granted=True, token=lock_token)
        elif lock_holder == request.worker_id:
            # Worker already holds the lock (e.g. duplicate request) — idempotent
            return AcquireResponse(granted=True, token=lock_token)
        else:
            # Lock is held by someone else — enqueue if not already waiting
            if request.worker_id not in lock_queue:
                lock_queue.append(request.worker_id)
            position = list(lock_queue).index(request.worker_id) + 1
            return AcquireResponse(granted=False, position=position)


@app.post("/release", response_model=ReleaseResponse)
def release_lock(request: ReleaseRequest):
    """
    Release the lock.

    - Validates that the requester is the current holder and the token matches.
    - On success, grants the lock to the next worker in the queue (if any).
    """
    with _state_lock:
        if lock_holder is None:
            return ReleaseResponse(released=False, error="No lock is currently held.")
        if lock_holder != request.worker_id:
            return ReleaseResponse(
                released=False,
                error=f"Worker {request.worker_id} does not hold the lock.",
            )
        if lock_token != request.token:
            return ReleaseResponse(released=False, error="Invalid token.")

        logger.info("Lock released by %s (token=%s)", request.worker_id, request.token)
        _grant_next()
        return ReleaseResponse(released=True)


@app.get("/status", response_model=StatusResponse)
def get_status():
    """Return the current lock holder, queue, and active token."""
    with _state_lock:
        return StatusResponse(
            holder=lock_holder,
            queue=list(lock_queue),
            token=lock_token,
        )


# DONT MODIFY THIS ENDPOINT
@app.get("/health")
def health():
    """Health check endpoint for Docker."""
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Part 2 Endpoints (Fault Tolerance)
# ---------------------------------------------------------------------------

@app.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(request: HeartbeatRequest):
    """
    Refresh the heartbeat for the current lock holder.

    Returns valid=True if the worker still holds the lock with a matching token.
    """
    global last_heartbeat

    with _state_lock:
        if lock_holder != request.worker_id:
            return HeartbeatResponse(
                valid=False,
                error=f"Worker {request.worker_id} does not hold the lock.",
            )
        if lock_token != request.token:
            return HeartbeatResponse(valid=False, error="Token mismatch.")

        last_heartbeat = time.monotonic()
        return HeartbeatResponse(valid=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
    