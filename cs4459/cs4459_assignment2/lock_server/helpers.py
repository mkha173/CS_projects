"""
Lock Server Helpers — DO NOT MODIFY THIS FILE

This module provides helper functions used by the lock server.
Students must NOT edit this file. These functions are used internally
for fencing token generation and audit logging.
"""

import os
import logging
import threading
import psycopg2

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
def _get_db_connection():
    """Create a new database connection."""
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


# ---------------------------------------------------------------------------
# Fencing token generation
# ---------------------------------------------------------------------------
_token_counter: int = 0
_token_lock = threading.Lock()


def generate_token(worker_id: str) -> str:
    """
    Generate a new fencing token and log the grant to lock_history.

    Call this function every time you grant lock access to a worker.
    It increments the global token counter, records the grant in the
    database, and returns the token string. Thread-safe.

    Args:
        worker_id: The worker being granted the lock.

    Returns:
        The new fencing token as a string (e.g. "1", "2", "3", ...).
    """
    global _token_counter
    with _token_lock:
        _token_counter += 1
        token = str(_token_counter)
    try:
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO lock_history (worker_id, token, action) "
                    "VALUES (%s, %s, %s)",
                    (worker_id, token, "granted"),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error("Failed to log lock grant: %s", e)
    return token
