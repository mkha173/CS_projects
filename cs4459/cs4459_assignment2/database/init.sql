-- Concert Ticket Booking: Seat Initialization
-- This script runs automatically when the PostgreSQL container starts.

CREATE TABLE IF NOT EXISTS seats (
    seat_id     VARCHAR(10) PRIMARY KEY,
    status      VARCHAR(20) NOT NULL DEFAULT 'available',
    booked_by   VARCHAR(100),
    token       VARCHAR(100),
    booked_at   TIMESTAMP
);

-- Append-only log of all booking operations (used to verify double bookings)
CREATE TABLE IF NOT EXISTS booking_history (
    id          SERIAL PRIMARY KEY,
    seat_id     VARCHAR(10) NOT NULL,
    agent_id    VARCHAR(100) NOT NULL,
    token       VARCHAR(100),
    action      VARCHAR(20) NOT NULL,   -- 'booked', 'rejected_stale', 'rejected_unavailable', 'rejected_not_found'
    detail      TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Append-only log of all lock operations (used to verify FIFO ordering)
CREATE TABLE IF NOT EXISTS lock_history (
    id          SERIAL PRIMARY KEY,
    worker_id   VARCHAR(100) NOT NULL,
    token       VARCHAR(100),
    action      VARCHAR(20) NOT NULL DEFAULT 'granted',
    detail      TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert 50 seats: A1 through A50
INSERT INTO seats (seat_id) VALUES
    ('A1'),  ('A2'),  ('A3'),  ('A4'),  ('A5'),
    ('A6'),  ('A7'),  ('A8'),  ('A9'),  ('A10'),
    ('A11'), ('A12'), ('A13'), ('A14'), ('A15'),
    ('A16'), ('A17'), ('A18'), ('A19'), ('A20'),
    ('A21'), ('A22'), ('A23'), ('A24'), ('A25'),
    ('A26'), ('A27'), ('A28'), ('A29'), ('A30'),
    ('A31'), ('A32'), ('A33'), ('A34'), ('A35'),
    ('A36'), ('A37'), ('A38'), ('A39'), ('A40'),
    ('A41'), ('A42'), ('A43'), ('A44'), ('A45'),
    ('A46'), ('A47'), ('A48'), ('A49'), ('A50');
