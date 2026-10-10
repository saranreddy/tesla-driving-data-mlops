# 🥈 Silver Layer — Quality Checks & Data Cleaning

## Overview

The silver layer applies quality checks and data cleaning to bronze layer data. Every check from GitHub issue #11 is implemented here. Data is written to `s3://<bucket>/silver/` and cataloged in the `teslamate_silver` Glue database.

## Input

- **Source:** Bronze layer (`s3://<bucket>/bronze/`)
- **Tables:** `drives`, `positions`

## Output Tables

### silver_drives
- **Location:** `s3://<bucket>/silver/drives/date=YYYY-MM-DD/`
- **Description:** Cleaned drives with quality flags
- **Schema:** All bronze `drives` columns plus:
  - `quality_flag` (boolean): `true` if any check failed
  - `pct_usable` (double): Percentage of checks passed (0-100)
  - `failure_reasons` (string): Comma-separated list of failed checks

### silver_positions
- **Location:** `s3://<bucket>/silver/positions/date=YYYY-MM-DD/`
- **Description:** Cleaned position readings with forward-filled sparse fields
- **Schema:** Same as bronze `positions`

### silver_run_status
- **Location:** `s3://<bucket>/silver/_metadata/run_status/date=YYYY-MM-DD/`
- **Description:** Per-run execution metadata
- **Schema:**
  - `run_date` (timestamp): When the silver job ran
  - `process_date` (string): Date being processed
  - `success` (boolean): Whether processing succeeded
  - `message` (string): Success message or error details

## Quality Checks

All checks from [GitHub issue #11](https://github.com/saranreddy/tesla-driving-data-mlops/issues/11):

### 1. Energy Plausibility
- **Check:** Does `kwh_used` match battery % drop times pack size?
- **Logic:** Implied pack size = `(kwh_used / battery_pct_drop) × 100`
- **Pass:** Pack size between 50-120 kWh (covers Model 3 SR to Model S/X)
- **Fail reason:** `energy_implausible`

### 2. Efficiency Range
- **Check:** Is `efficiency` in plausible range?
- **Logic:** `100 <= efficiency <= 500` Wh/km
- **Pass:** Within range (covers eco driving to aggressive driving)
- **Fail reason:** `efficiency_out_of_range`

### 3. Trip Length
- **Check:** Is trip long enough to be meaningful?
- **Logic:** `distance >= 1.6 km` AND `duration >= 2 min`
- **Pass:** Meets both thresholds
- **Fail reason:** `trip_too_short`

### 4. Odometer Consistency
- **Check:** Does odometer delta match reported distance?
- **Logic:** `abs(odometer_delta - distance) / distance <= 10%`
- **Pass:** Within 10% tolerance
- **Fail reason:** `odometer_mismatch`

### Planned (Not Yet Implemented)
- Gap detection (>10s between readings)
- Impossible speed jumps (>20 mph/s acceleration)
- GPS jumps (teleportation detection)
- Duplicate timestamps

## Transformations

### From Bronze to Silver

1. **Quality Scoring:**
   - Each drive gets a `quality_flag` (any check fails → `true`)
   - `pct_usable` = (passing checks / total checks) × 100
   - `failure_reasons` lists which checks failed

2. **Forward-Filling (positions):**
   - Sparse fields filled within each `drive_id`:
     - `ideal_battery_range_km`
     - `battery_level`
     - `outside_temp`
     - `fan_status`, `driver_temp_setting`, `passenger_temp_setting`
   - Never propagates across different drives

3. **No Filtering:**
   - Silver layer keeps ALL data, even flagged trips
   - Downstream consumers (gold layer) decide whether to skip flagged data

## Execution

**Script:** `teslamate_platform/silver/process_silver.py`

**Schedule:** Nightly after bronze export (9:05 PM CT)

**Command:**
```bash
/opt/teslamate/venv/bin/python /opt/teslamate/silver/process_silver.py \
  --s3-bucket <bucket-name> \
  --date YYYY-MM-DD
```

**Output:** Parquet files in `s3://<bucket>/silver/`

## Data Quality Guarantees

- ✅ **Schema validated:** Explicit PyArrow schemas match Glue catalog
- ✅ **Quality tracked:** Every trip has quality_flag and reasons
- ✅ **Auditable:** Run status table records every execution
- ✅ **Sparse fields filled:** Forward-fill within trips, never across
- ⚠️ **No data dropped:** Flagged trips kept for investigation

## Querying Silver Data

### All Good Drives
```sql
SELECT *
FROM teslamate_silver.silver_drives
WHERE quality_flag = false
  AND date = '2026-10-09'
```

### Investigate Flagged Trips
```sql
SELECT id, distance, kwh_used, efficiency,
       pct_usable, failure_reasons
FROM teslamate_silver.silver_drives
WHERE quality_flag = true
  AND date = '2026-10-09'
ORDER BY pct_usable ASC
```

### Check Run Status
```sql
SELECT *
FROM teslamate_silver.silver_run_status
WHERE date = '2026-10-09'
```

## Next Step

➡️ **Gold Layer** (`usecases/insurance/gold/`) extracts features and scores for specific use cases, skipping flagged trips
