CREATE SCHEMA IF NOT EXISTS bayan_runtime;

CREATE TABLE IF NOT EXISTS bayan_runtime.request_buckets (
    subject_key text NOT NULL,
    window_seconds integer NOT NULL,
    window_start bigint NOT NULL,
    request_count integer NOT NULL CHECK (request_count >= 0),
    PRIMARY KEY (subject_key, window_seconds, window_start)
);

CREATE TABLE IF NOT EXISTS bayan_runtime.request_leases (
    lease_id uuid PRIMARY KEY,
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS request_leases_expires_at_idx
    ON bayan_runtime.request_leases (expires_at);
