"""
Booking Service Helpers — DO NOT MODIFY THIS FILE

This module provides helper functions used by the booking service.
Students must NOT edit this file. These functions handle the atomic
seat booking and audit logging.
"""

import os
import logging

import psycopg2
import psycopg2.extras

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "database")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "tickets")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------
def get_db_connection():
    """Create a new database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


# ---------------------------------------------------------------------------
# Pydantic model (needed by update_ticket return type)
# ---------------------------------------------------------------------------
from pydantic import BaseModel


class BookResponse(BaseModel):
    success: bool
    seat_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Booking history logger
# ---------------------------------------------------------------------------
def _log_booking(conn, seat_id: str, agent_id: str, token: str, action: str, detail: str | None = None):
    """Log a booking event to the booking_history table."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO booking_history (seat_id, agent_id, token, action, detail) "
            "VALUES (%s, %s, %s, %s, %s)",
            (seat_id, agent_id, token, action, detail),
        )


# ---------------------------------------------------------------------------
# Ticket update helper
# ---------------------------------------------------------------------------
def update_ticket(seat_id: str, agent_id: str, token: str) -> BookResponse:
    """
    Attempt to book a seat and log the result to booking_history.

    This function performs an atomic UPDATE on the seats table (only if the
    seat is currently 'available') and appends an entry to the booking_history
    table regardless of the outcome.

    Args:
        seat_id:  The seat to book (e.g. "A3").
        agent_id: The worker/agent requesting the booking.
        token:    The fencing token from the lock server.

    Returns:
        A BookResponse indicating success or failure.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE seats SET status = 'booked', booked_by = %s, token = %s, "
                "booked_at = NOW() WHERE seat_id = %s AND status = 'available'",
                (agent_id, token, seat_id),
            )
            conn.commit()

            if cur.rowcount == 1:
                _log_booking(conn, seat_id, agent_id, token, "booked")
                conn.commit()
                logger.info("Seat %s booked by %s (token %s)", seat_id, agent_id, token)
                return BookResponse(success=True, seat_id=seat_id)

            # Determine why the update matched 0 rows
            cur.execute("SELECT seat_id, status FROM seats WHERE seat_id = %s", (seat_id,))
            row = cur.fetchone()

            if row is None:
                return BookResponse(success=False, seat_id=seat_id, error="SEAT_NOT_FOUND")
            return BookResponse(success=False, seat_id=seat_id, error="SEAT_NOT_AVAILABLE")
    finally:
        conn.close()
