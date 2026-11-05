-- Minimal persistent inventory schema for NexTrace Stage 8 (PostgreSQL)
CREATE TABLE IF NOT EXISTS inventory_reservations (
    reservation_id VARCHAR(64) PRIMARY KEY,
    sku VARCHAR(128) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    request_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'RESERVED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
