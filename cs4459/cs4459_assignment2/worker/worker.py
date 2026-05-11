"""
Worker (Booking Agent)
"""

import os
import sys
import time
import logging
import threading
import requests

# ---------------------------------------------------------------------------
# Configuration (passed via environment variables from Docker Compose) 
# DONT MODIFY
# ---------------------------------------------------------------------------
LOCK_SERVER_URL = os.environ.get("LOCK_SERVER_URL", "http://lock-server:6000")
BOOKING_SERVICE_URL = os.environ.get("BOOKING_SERVICE_URL", "http://booking-service:8000")
WORKER_ID = os.environ.get("HOSTNAME", "worker-unknown")
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 5))
RETRY_DELAY = float(os.environ.get("RETRY_DELAY", 1.0))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", 0.5))

logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [{WORKER_ID}] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: Wait for services to be ready
# DONT MODIFY THIS METHOD
# ---------------------------------------------------------------------------
def wait_for_services():
    """
    Block until both the Lock Server and Booking Service are healthy.
    Retries with exponential backoff up to MAX_RETRIES times.
    """
    services = {
        "Lock Server": f"{LOCK_SERVER_URL}/health",
        "Booking Service": f"{BOOKING_SERVICE_URL}/health",
    }
    for name, url in services.items():
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    logger.info("%s is ready.", name)
                    break
            except requests.ConnectionError:
                pass
            delay = RETRY_DELAY * (2 ** attempt)
            logger.info("Waiting for %s (attempt %d/%d)...", name, attempt + 1, MAX_RETRIES)
            time.sleep(delay)
        else:
            logger.error("Could not connect to %s after %d attempts. Exiting.", name, MAX_RETRIES)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Part 1: Lock operations
# ---------------------------------------------------------------------------

def acquire_lock() -> str | None:
    """
    Acquire the lock from the Lock Server, polling until granted.

    Returns the fencing token string on success, or None on failure.
    """
    logger.info("Attempting to acquire lock...")
    while True:
        try:
            resp = requests.post(
                f"{LOCK_SERVER_URL}/acquire",
                json={"worker_id": WORKER_ID},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("granted"):
                token = data["token"]
                logger.info("Lock acquired (token=%s)", token)
                return token
            else:
                position = data.get("position", "?")
                logger.debug("Lock not granted, queue position=%s. Retrying in %.1fs...", position, POLL_INTERVAL)
                time.sleep(POLL_INTERVAL)
        except requests.RequestException as e:
            logger.error("Error acquiring lock: %s. Retrying in %.1fs...", e, RETRY_DELAY)
            time.sleep(RETRY_DELAY)


def release_lock(token: str) -> bool:
    """
    Release the lock on the Lock Server.

    Returns True if successfully released, False otherwise.
    """
    try:
        resp = requests.post(
            f"{LOCK_SERVER_URL}/release",
            json={"worker_id": WORKER_ID, "token": token},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("released"):
            logger.info("Lock released (token=%s)", token)
            return True
        else:
            logger.error("Failed to release lock: %s", data.get("error"))
            return False
    except requests.RequestException as e:
        logger.error("Error releasing lock: %s", e)
        return False


# ---------------------------------------------------------------------------
# Part 1: Booking operations
# ---------------------------------------------------------------------------

def get_available_seats() -> list[dict]:
    """
    Fetch the list of available seats from the Booking Service.

    Returns a list of seat dicts, e.g. [{"seat_id": "A3", "status": "available"}, ...]
    """
    try:
        resp = requests.get(f"{BOOKING_SERVICE_URL}/seats/available", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Error fetching available seats: %s", e)
        return []


def book_seat(seat_id: str, token: str) -> bool:
    """
    Book a specific seat via the Booking Service.

    Returns True if booking succeeded, False otherwise.
    """
    try:
        resp = requests.post(
            f"{BOOKING_SERVICE_URL}/book",
            json={"seat_id": seat_id, "agent_id": WORKER_ID, "token": token},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        success = data.get("success", False)
        if success:
            logger.info("Successfully booked seat %s (token=%s)", seat_id, token)
        else:
            logger.warning("Failed to book seat %s: %s", seat_id, data.get("message", "unknown reason"))
        return success
    except requests.RequestException as e:
        logger.error("Error booking seat %s: %s", seat_id, e)
        return False


# ---------------------------------------------------------------------------
# Part 2: Heartbeat (Fault Tolerance)
# ---------------------------------------------------------------------------

def start_heartbeat(token: str, stop_event: threading.Event) -> threading.Thread:
    """
    Start a background heartbeat thread.

    The thread sends POST /heartbeat every 500ms until stop_event is set.
    Returns the thread object.
    """
    def _heartbeat_loop():
        while not stop_event.wait(0.5):
            try:
                resp = requests.post(
                    f"{LOCK_SERVER_URL}/heartbeat",
                    json={"worker_id": WORKER_ID, "token": token},
                    timeout=3,
                )
                data = resp.json()
                if not data.get("valid"):
                    logger.warning("Heartbeat rejected: %s", data.get("error"))
                    stop_event.set()
                    return
            except requests.RequestException as e:
                logger.error("Heartbeat request failed: %s", e)

    t = threading.Thread(target=_heartbeat_loop, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    """
    Main worker loop: acquire lock → book a seat → release lock → repeat.
    Continues until no seats remain.
    """
    logger.info("Worker %s starting...", WORKER_ID)
    wait_for_services()

    while True:
        # Step 1: Acquire the lock
        token = acquire_lock()
        if token is None:
            logger.error("Could not acquire lock. Exiting.")
            break

        # Part 2: Start heartbeat thread
        stop_heartbeat = threading.Event()
        heartbeat_thread = start_heartbeat(token, stop_heartbeat)
        revoked = False

        try:
            # Step 2: Get available seats
            seats = get_available_seats()

            # Step 3: No seats left — we're done
            if not seats:
                logger.info("No seats available. Worker %s exiting.", WORKER_ID)
                # Stop heartbeat cleanly before releasing
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=2.0)
                release_lock(token)
                break

            # Step 4: Pick first available seat
            seat_id = seats[0]["seat_id"]
            logger.info("Attempting to book seat %s", seat_id)

            # Step 5: Check if lock was revoked before we even try booking
            if stop_heartbeat.is_set():
                logger.warning("Lock was revoked before booking. Re-acquiring...")
                revoked = True
            else:
                book_seat(seat_id, token)

                # Check again after booking in case revocation happened mid-flight
                if stop_heartbeat.is_set():
                    logger.warning("Lock was revoked during/after booking.")
                    revoked = True

        except Exception as e:
            logger.exception("Unexpected error during booking cycle: %s", e)

        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=2.0)
            if not revoked:
                release_lock(token)
            else:
                logger.info("Skipping release — lock was already revoked (token=%s).", token)

    logger.info("Worker %s finished.", WORKER_ID)


if __name__ == "__main__":
    main()