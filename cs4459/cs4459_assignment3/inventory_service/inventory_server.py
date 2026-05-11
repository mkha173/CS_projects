"""
CS 4459: Assignment 3 — Inventory Service
Manages the shared inventory database.

Provided endpoints: GET /inventory/available, GET /inventory/summary, GET /access-log
You implement:      POST /process-order (with idempotency)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from helpers import get_db_connection

app = FastAPI()


# --- Request/Response Models ---

class OrderRequest(BaseModel):
    worker_id: int
    item_id: int
    idempotency_key: str


# ============================================================
#  PROVIDED ENDPOINTS — DO NOT MODIFY
# ============================================================

@app.get("/inventory/available")
def get_available():
    """Returns items currently available for purchase."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_id, item_name, quantity FROM inventory WHERE status = 'available' ORDER BY item_id"
    )
    rows = cursor.fetchall()
    conn.close()

    items = [{"item_id": r[0], "item_name": r[1], "quantity": r[2]} for r in rows]
    return {"items": items, "count": len(items)}


@app.get("/inventory/summary")
def get_summary():
    """Returns an overview of inventory state."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM inventory")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM inventory WHERE status = 'available'")
    available = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM inventory WHERE status = 'sold_out'")
    sold = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM order_history")
    orders = cursor.fetchone()[0]

    conn.close()

    return {
        "total_items": total,
        "available": available,
        "sold": sold,
        "orders_processed": orders,
    }


@app.get("/access-log")
def get_access_log():
    """Returns the access audit log for mutual exclusion verification."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT log_id, worker_id, action, timestamp FROM access_log ORDER BY log_id"
    )
    rows = cursor.fetchall()
    conn.close()

    entries = [
        {
            "log_id": r[0],
            "worker_id": r[1],
            "action": r[2],
            "timestamp": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]
    return {"entries": entries, "count": len(entries)}


# ============================================================
#  POST /process-order — Idempotent order processing
# ============================================================

@app.post("/process-order")
def process_order(order: OrderRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Log entry into the critical section
        cursor.execute(
            "INSERT INTO access_log (worker_id, action) VALUES (%s, 'enter')",
            (order.worker_id,)
        )
        conn.commit()

        # Step 2: Check idempotency — has this key been seen before?
        cursor.execute(
            "SELECT order_id, item_id, worker_id FROM order_history WHERE idempotency_key = %s",
            (order.idempotency_key,)
        )
        existing = cursor.fetchone()
        if existing:
            # Duplicate request — return the original result unchanged
            cursor.execute(
                "INSERT INTO access_log (worker_id, action) VALUES (%s, 'exit')",
                (order.worker_id,)
            )
            conn.commit()
            return {
                "success": True,
                "order_id": existing[0],
                "item_id": existing[1],
                "worker_id": existing[2],
                "duplicate": True,
            }

        # Step 3: Validate — check the item exists and is still available
        cursor.execute(
            "SELECT item_id, quantity, status FROM inventory WHERE item_id = %s",
            (order.item_id,)
        )
        item = cursor.fetchone()
        if not item or item[2] != "available" or item[1] <= 0:
            cursor.execute(
                "INSERT INTO access_log (worker_id, action) VALUES (%s, 'exit')",
                (order.worker_id,)
            )
            conn.commit()
            return {
                "success": False,
                "reason": "item_unavailable",
                "item_id": order.item_id,
            }

        # Step 4: Process — mark item sold and record the order
        cursor.execute(
            "UPDATE inventory SET quantity = 0, status = 'sold_out' WHERE item_id = %s",
            (order.item_id,)
        )
        cursor.execute(
            """
            INSERT INTO order_history (item_id, worker_id, idempotency_key)
            VALUES (%s, %s, %s)
            RETURNING order_id
            """,
            (order.item_id, order.worker_id, order.idempotency_key)
        )
        order_id = cursor.fetchone()[0]
        conn.commit()

        # Step 5: Log exit from the critical section
        cursor.execute(
            "INSERT INTO access_log (worker_id, action) VALUES (%s, 'exit')",
            (order.worker_id,)
        )
        conn.commit()

        return {
            "success": True,
            "order_id": order_id,
            "item_id": order.item_id,
            "worker_id": order.worker_id,
            "duplicate": False,
        }

    except Exception as e:
        conn.rollback()
        # Best-effort exit log so the audit trail is not left hanging open
        try:
            cursor.execute(
                "INSERT INTO access_log (worker_id, action) VALUES (%s, 'exit')",
                (order.worker_id,)
            )
            conn.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()