CREATE SCHEMA IF NOT EXISTS bayan;
CREATE TABLE bayan.schema_version (
 version integer PRIMARY KEY CHECK (version = 1),
 migration_sha256 text NOT NULL
);
CREATE TABLE bayan.active_snapshot (
 singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
 snapshot_id text NOT NULL REFERENCES adrec_intake.snapshots(snapshot_id)
);
CREATE VIEW bayan.transactions WITH (security_barrier=true) AS
SELECT t.* FROM adrec_intake.transactions t
JOIN bayan.active_snapshot a USING (snapshot_id);
CREATE VIEW bayan.price_indices WITH (security_barrier=true) AS
SELECT p.* FROM adrec_intake.price_indices p
JOIN bayan.active_snapshot a USING (snapshot_id);
-- Keep original observations separate: no assumed annualization or joined averages.
CREATE VIEW bayan.rental_observations WITH (security_barrier=true) AS
SELECT r.* FROM adrec_intake.rental_observations r
JOIN bayan.active_snapshot a USING (snapshot_id);
CREATE VIEW bayan.dataset_coverage WITH (security_barrier=true) AS
SELECT s.snapshot_id, s.source_file, s.sha256, s.retrieved_at, s.source_rows,
 s.grain, s.measure, s.complete_through,
 min(COALESCE(o.dimensions->>'Sale Application Date',o.dimensions->>'Date',o.dimensions->>'End of Period'))::date AS observed_from,
 max(COALESCE(o.dimensions->>'Sale Application Date',o.dimensions->>'Date',o.dimensions->>'End of Period'))::date AS observed_through
FROM adrec_intake.sources s
JOIN bayan.active_snapshot a USING(snapshot_id)
JOIN adrec_intake.observations o USING(snapshot_id,source_file)
GROUP BY s.snapshot_id,s.source_file,s.sha256,s.retrieved_at,s.source_rows,s.grain,s.measure,s.complete_through;
