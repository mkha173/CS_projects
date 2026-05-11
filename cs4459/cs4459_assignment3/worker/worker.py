"""
CS 4459: Assignment 3 — Worker Service
Distributed Order Processing with Message-Based Coordination

Each worker is a FastAPI microservice that coordinates with peers
using REQUEST/REPLY messages and Lamport logical clocks to ensure
mutual exclusion when accessing the inventory service.
"""

from fastapi import FastAPI
import os
import requests
import threading
import uuid

app = FastAPI()

# --- Environment Variables (set by Docker Compose — DO NOT MODIFY) ---
WORKER_ID = int(os.environ["WORKER_ID"])
NUM_WORKERS = int(os.environ["NUM_WORKERS"])
NUM_ORDERS = int(os.environ.get("NUM_ORDERS", "50"))
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://inventory-service:8000")


def get_peer_url(worker_id: int) -> str:
    """Returns the base URL for a peer worker."""
    return f"http://worker-{worker_id}:{5000 + worker_id}"


# --- Coordination State ---
# Use state_lock to protect all coordination state.
# Multiple threads access this state: the /start processing loop,
# the /request handler, and the /reply handler.

state_lock = threading.Lock()
clock = 0
state = "RELEASED"          # "RELEASED", "WANTED", or "HELD"
request_timestamp = None    # Clock value when we requested access
replies_received = 0        # Count of REPLY messages for current request
deferred_queue = []         # Worker IDs whose REPLY we deferred

# Event to signal when all replies have been received.
# acquire() waits on this; the /reply handler sets it.
all_replies = threading.Event()


# ============================================================
#  Coordination Functions
# ============================================================

def acquire():
    """
    Rule 1: Request access to the critical section.
    Sets state to WANTED, increments clock, records timestamp,
    sends REQUEST to all peers, waits for N-1 REPLYs.
    """
    global clock, state, request_timestamp, replies_received

    # Update shared state under the lock, then release before making HTTP calls
    with state_lock:
        clock += 1
        request_timestamp = clock
        state = "WANTED"
        replies_received = 0
        all_replies.clear()
        snapshot_ts = request_timestamp

    peers = [i for i in range(1, NUM_WORKERS + 1) if i != WORKER_ID]

    # Send REQUEST to every peer (never hold state_lock during HTTP calls)
    for peer_id in peers:
        try:
            requests.post(
                f"{get_peer_url(peer_id)}/request",
                json={"timestamp": snapshot_ts, "sender_id": WORKER_ID},
                timeout=10,
            )
        except Exception as e:
            print(f"[Worker {WORKER_ID}] ERROR sending REQUEST to Worker {peer_id}: {e}")

    # If we are the only worker there are no peers to wait for
    if not peers:
        with state_lock:
            state = "HELD"
        return

    # Block until the /reply handler signals that all N-1 replies have arrived
    all_replies.wait()

    with state_lock:
        state = "HELD"


def release():
    """
    Rule 4: Release access to the critical section.
    Sets state to RELEASED, sends REPLY to all deferred peers.
    """
    global state, deferred_queue

    with state_lock:
        state = "RELEASED"
        pending = list(deferred_queue)
        deferred_queue.clear()
        ts = clock

    # Send deferred replies outside the lock
    for peer_id in pending:
        try:
            requests.post(
                f"{get_peer_url(peer_id)}/reply",
                json={"timestamp": ts, "sender_id": WORKER_ID},
                timeout=10,
            )
        except Exception as e:
            print(f"[Worker {WORKER_ID}] ERROR sending deferred REPLY to Worker {peer_id}: {e}")


# ============================================================
#  Message Handlers
# ============================================================

@app.post("/request")
def handle_request(body: dict):
    """
    Rule 2: Receives REQUEST(timestamp, sender_id) from a peer.
    Reply immediately unless we are HELD, or we are WANTED with
    higher priority — in that case defer until release().

    Priority: lower (timestamp, worker_id) tuple wins.
    """
    global clock, deferred_queue

    their_ts = body["timestamp"]
    sender_id = body["sender_id"]
    reply_now = False
    ts_to_send = None

    with state_lock:
        # Lamport clock update on receive
        clock = max(clock, their_ts) + 1

        if state == "HELD":
            # We are inside the critical section — always defer
            deferred_queue.append(sender_id)
        elif state == "WANTED":
            # Compare priority tuples: lower = higher priority
            our_tuple   = (request_timestamp, WORKER_ID)
            their_tuple = (their_ts, sender_id)
            if our_tuple < their_tuple:
                # We have higher priority — defer their request
                deferred_queue.append(sender_id)
            else:
                # They have higher priority — reply immediately
                reply_now = True
                ts_to_send = clock
        else:
            # RELEASED — not competing, reply immediately
            reply_now = True
            ts_to_send = clock

    if reply_now:
        try:
            requests.post(
                f"{get_peer_url(sender_id)}/reply",
                json={"timestamp": ts_to_send, "sender_id": WORKER_ID},
                timeout=10,
            )
        except Exception as e:
            print(f"[Worker {WORKER_ID}] ERROR sending REPLY to Worker {sender_id}: {e}")

    return {"status": "ok"}


@app.post("/reply")
def handle_reply(body: dict):
    """
    Rule 3: Receives REPLY(timestamp, sender_id) from a peer.
    Updates Lamport clock and increments reply counter.
    Signals all_replies once N-1 replies have been received.
    """
    global clock, replies_received

    their_ts = body["timestamp"]

    with state_lock:
        clock = max(clock, their_ts) + 1
        replies_received += 1
        got_all = replies_received >= (NUM_WORKERS - 1)

    if got_all:
        all_replies.set()

    return {"status": "ok"}


# ============================================================
#  Other Endpoints
# ============================================================

@app.get("/state")
def get_state():
    """Returns current coordination state for debugging and grading."""
    with state_lock:
        return {
            "worker_id":        WORKER_ID,
            "clock":            clock,
            "state":            state,
            "request_timestamp": request_timestamp,
            "replies_received": replies_received,
            "deferred_count":   len(deferred_queue),
        }


@app.post("/start")
def start():
    """
    Triggers the order-processing loop.
    Loops NUM_ORDERS times: acquire → fetch available item →
    POST /process-order → release.  Stops early when no items remain.
    Returns: {"status": "completed", "worker_id": ..., "orders_processed": ...}
    """
    orders_processed = 0

    for _ in range(NUM_ORDERS):
        acquire()

        try:
            # fetch an available item while holding the critical section
            resp = requests.get(f"{INVENTORY_URL}/inventory/available", timeout=10)
            items = resp.json().get("items", [])

            if not items:
                # nothing left to sell — exit early
                release()
                break

            item_id = items[0]["item_id"]
            idempotency_key = f"worker-{WORKER_ID}-{uuid.uuid4()}"

            order_resp = requests.post(
                f"{INVENTORY_URL}/process-order",
                json={
                    "worker_id":       WORKER_ID,
                    "item_id":         item_id,
                    "idempotency_key": idempotency_key,
                },
                timeout=10,
            )
            result = order_resp.json()
            if result.get("success"):
                orders_processed += 1

        except Exception as e:
            print(f"[Worker {WORKER_ID}] ERROR during order processing: {e}")

        finally:
            release()

    return {
        "status":           "completed",
        "worker_id":        WORKER_ID,
        "orders_processed": orders_processed,
    }


@app.get("/peers")
def get_peers():
    """Returns the list of peer worker URLs."""
    peers = [
        {"worker_id": i, "url": get_peer_url(i)}
        for i in range(1, NUM_WORKERS + 1)
        if i != WORKER_ID
    ]
    return {"worker_id": WORKER_ID, "peers": peers}