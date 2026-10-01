-- Separate intake schema: apply only to an explicitly selected staging target.
-- No synthetic dimensions or grants to the application's query role.
CREATE SCHEMA IF NOT EXISTS adrec_intake;
CREATE TABLE IF NOT EXISTS adrec_intake.snapshots (
    snapshot_id text PRIMARY KEY,
    contract_version integer NOT NULL,
    contract_sha256 text NOT NULL CHECK (length(contract_sha256) = 64),
    status text NOT NULL CHECK (status IN ('staging', 'validated', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS adrec_intake.sources (
    snapshot_id text NOT NULL REFERENCES adrec_intake.snapshots,
    source_file text NOT NULL,
    sha256 text NOT NULL CHECK (length(sha256) = 64),
    retrieved_at timestamptz NOT NULL,
    source_rows integer NOT NULL CHECK (source_rows >= 0),
    grain text NOT NULL,
    measure text NOT NULL,
    complete_through date,
    PRIMARY KEY (snapshot_id, source_file)
);
CREATE TABLE IF NOT EXISTS adrec_intake.observations (
    snapshot_id text NOT NULL,
    source_file text NOT NULL,
    source_row integer NOT NULL CHECK (source_row > 0),
    dimensions jsonb NOT NULL,
    metrics jsonb NOT NULL,
    quality_flags jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (snapshot_id, source_file, source_row),
    FOREIGN KEY (snapshot_id, source_file)
        REFERENCES adrec_intake.sources (snapshot_id, source_file)
);
COMMENT ON TABLE adrec_intake.observations IS
'Lossless source observations, not a public analytical surface. Row ordinal identifies a row only within the checksummed snapshot; never deduplicate sales by visible values.';
