BEGIN;

ALTER TABLE anomalies
    ADD COLUMN start_timestamp_ms BIGINT,
    ADD COLUMN end_timestamp_ms BIGINT;

UPDATE anomalies AS anomaly
SET start_timestamp_ms = start_point.timestamp_ms,
    end_timestamp_ms = end_point.timestamp_ms
FROM telemetry_points AS start_point,
     telemetry_points AS end_point
WHERE start_point.id = anomaly.start_telemetry_point_id
  AND end_point.id = anomaly.end_telemetry_point_id;

ALTER TABLE anomalies
    ALTER COLUMN start_timestamp_ms SET NOT NULL,
    ALTER COLUMN end_timestamp_ms SET NOT NULL,
    ADD CONSTRAINT ck_anomalies_timestamp_range
        CHECK (start_timestamp_ms <= end_timestamp_ms),
    DROP COLUMN start_telemetry_point_id,
    DROP COLUMN end_telemetry_point_id;

COMMIT;
