-- CS 4459: Assignment 3 — Database Schema
-- DO NOT MODIFY THIS FILE

-- Inventory: 200 items, each with quantity 1
CREATE TABLE inventory (
    item_id SERIAL PRIMARY KEY,
    item_name VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'available'
);

-- Order history: records every successful order
CREATE TABLE order_history (
    order_id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES inventory(item_id),
    worker_id INTEGER NOT NULL,
    idempotency_key VARCHAR(100) UNIQUE,
    processed_at TIMESTAMP DEFAULT NOW()
);

-- Access log: audit trail for mutual exclusion verification
CREATE TABLE access_log (
    log_id SERIAL PRIMARY KEY,
    worker_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Seed 200 items
INSERT INTO inventory (item_name, quantity, status)
SELECT
    'Item-' || LPAD(i::text, 3, '0'),
    1,
    'available'
FROM generate_series(1, 200) AS i;