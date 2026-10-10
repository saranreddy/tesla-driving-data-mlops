# Feature Extraction

**Status:** Placeholder. No code yet.

## Purpose

Extract per-trip risk features from TeslaMate drives data for the insurance scoring use case.

## Planned Features

1. **Hard Braking Count** — Number of events where deceleration exceeds threshold (e.g., -0.4 g)
2. **Hard Acceleration Count** — Number of events where acceleration exceeds threshold (e.g., 0.3 g)
3. **Speeding Duration (minutes)** — Time spent above estimated speed limits
4. **Night Driving Share** — Proportion of trip duration between 10 PM and 5 AM
5. **Highway Share** — Proportion of distance at sustained high speeds (proxy for highway driving)

## Input

- **Source:** `s3://<bucket>/raw/drives/date=YYYY-MM-DD/drives.parquet`
- **Glue table:** `teslamate_mlops_data.drives`

## Output

- **Target:** `s3://<bucket>/usecases/insurance/features/date=YYYY-MM-DD/features.parquet`
- **Schema:** One row per trip with extracted features

## Implementation Notes

- Use SageMaker Processing job with pandas/pyarrow
- Extract features from available TeslaMate columns (speed_max, duration_min, start_date, end_date, distance)
- Where detailed telemetry is missing (e.g., acceleration data), use proxy signals or skip that feature
