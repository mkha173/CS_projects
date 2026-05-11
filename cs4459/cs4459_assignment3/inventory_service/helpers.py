"""
CS 4459: Assignment 3 — Inventory Service Helpers
DO NOT MODIFY THIS FILE
"""

import os
import psycopg2


def get_db_connection():
    """
    Returns a new psycopg2 connection to the PostgreSQL database.
    Uses environment variables set by Docker Compose.

    Usage:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ...")
        results = cursor.fetchall()
        conn.commit()
        conn.close()
    """
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "inventory"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
    )