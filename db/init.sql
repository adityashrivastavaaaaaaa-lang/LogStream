-- This script is run when the 'db' container is first created.

CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    level VARCHAR(50) NOT NULL,
    service VARCHAR(100) NOT NULL,
    message TEXT,
    metadata JSONB
);

-- Create indexes for faster querying
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs (level);
CREATE INDEX IF NOT EXISTS idx_logs_service ON logs (service);

-- Optional: Create an index for GIN operations on the metadata
CREATE INDEX IF NOT EXISTS idx_logs_metadata_gin ON logs USING GIN (metadata);
