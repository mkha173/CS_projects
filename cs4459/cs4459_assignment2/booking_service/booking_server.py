"""
Booking Service

A FastAPI service that wraps PostgreSQL to manage concert seat bookings.
Workers interact with this service via HTTP to check available seats and book them.
"""

import os
import time
import logging
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from helpers import get_db_connection, update_ticket, BookResponse  # DO NOT MODIFY helpers.py

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VALIDATE_TOKENS = os.environ.get("VALIDATE_TOKENS", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [booking-service] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def wait_for_db(max_retries: int = 30, delay: float = 1.0):
    """Block until PostgreSQL is accepting connections."""
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            conn.close()
            logger.info("Database is ready.")
            return
        except psycopg2.OperationalError:
            logger.info(
                "Waiting for database (attempt %d/%d)...", attempt + 1, max_retries
            )
            time.sleep(delay)
    raise RuntimeError("Could not connect to database after %d attempts" % max_retries)


# ---------------------------------------------------------------------------
# Fencing token tracking
# ---------------------------------------------------------------------------
highest_token_seen: int = 0

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class BookRequest(BaseModel):
    seat_id: str
    agent_id: str
    token: str


class SeatInfo(BaseModel):
    seat_id: str
    status: str
    booked_by: str | None = None


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    logger.info("Booking service started (VALIDATE_TOKENS=%s)", VALIDATE_TOKENS)
    yield


app = FastAPI(title="Booking Service", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
# DONT MODIFY THIS ENDPOINT
@app.get("/health")
def health():
    """Health check endpoint for Docker."""
    return {"status": "healthy"}

# DONT MODIFY THIS ENDPOINT
@app.get("/seats/available", response_model=list[SeatInfo])
def get_available_seats():
    """Return all seats that are currently available."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT seat_id, status, booked_by FROM seats "
                "WHERE status = 'available' ORDER BY seat_id"
            )
            rows = cur.fetchall()
        return [SeatInfo(**row) for row in rows]
    finally:
        conn.close()

# DONT MODIFY THIS ENDPOINT
@app.get("/seats", response_model=list[SeatInfo])
def get_all_seats(): 
    """Return all seats with their current status."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT seat_id, status, booked_by FROM seats ORDER BY seat_id"
            )
            rows = cur.fetchall()
        return [SeatInfo(**row) for row in rows]
    finally:
        conn.close()


@app.post("/book", response_model=BookResponse)
def book_seat(request: BookRequest):
    """
    Book a specific seat.

    Optionally validates fencing tokens when VALIDATE_TOKENS=true to reject
    stale operations from workers that lost the lock.
    """
    global highest_token_seen

    # --- Fencing token validation (Part 2) ---
    if VALIDATE_TOKENS:
        try:
            token_int = int(request.token)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid token format; must be an integer string.")

        if token_int < highest_token_seen:
            logger.warning(
                "Rejecting stale booking request from %s: token=%s < highest_seen=%d",
                request.agent_id, request.token, highest_token_seen,
            )
            raise HTTPException(
                status_code=409,
                detail=f"Stale fencing token {request.token}; current highest is {highest_token_seen}.",
            )

        highest_token_seen = token_int
        logger.info(
            "Token %s accepted for agent %s (highest_token_seen now %d)",
            request.token, request.agent_id, highest_token_seen,
        )

    # --- Attempt to book the seat (provided — do not modify) ---
    return update_ticket(request.seat_id, request.agent_id, request.token)


# ---------------------------------------------------------------------------
# Main DONT MODIFY
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
    