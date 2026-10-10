# 🥉 Bronze Layer — Raw Telemetry from TeslaMate

## Overview

The bronze layer contains raw data exported directly from TeslaMate's PostgreSQL database with minimal transformation. Data is written to `s3://<bucket>/bronze/` in Parquet format and cataloged in the `teslamate_bronze` Glue database.

## Input

- **Source:** TeslaMate PostgreSQL database
- **Tables:** `drives`, `charging_processes`, `positions`

## Output Tables

### drives
- **Location:** `s3://<bucket>/bronze/drives/date=YYYY-MM-DD/`
- **Partitioning:** By date (`start_date`)
- **Schema:**
  - `id` (bigint): Drive ID
  - `start_date`, `end_date` (timestamp): Trip start/end times (ms precision)
  - `start_address`, `end_address` (string): Address names
  - `distance` (double): Distance in km
  - `duration_min` (double): Duration in minutes
  - `start_km`, `end_km` (double): Odometer readings
  - `kwh_used` (double): Energy used in kWh (calculated: rated range delta × car efficiency)
  - `start_battery_level`, `end_battery_level` (int): Battery percentage
  - `outside_temp_avg` (double): Average outside temperature
  - `speed_max` (double): Maximum speed
  - `efficiency` (double): Trip efficiency in Wh/km

### charges
- **Location:** `s3://<bucket>/bronze/charges/date=YYYY-MM-DD/`
- **Partitioning:** By date (`start_date`)
- **Schema:**
  - `id` (bigint): Charge ID
  - `start_date`, `end_date` (timestamp): Charge start/end times (ms precision)
  - `address` (string): Charging location
  - `charge_energy_added` (double): Energy added in kWh
  - `start_battery_level`, `end_battery_level` (int): Battery percentage
  - `duration_min` (double): Charging duration in minutes
  - `cost` (double): Charging cost

### positions
- **Location:** `s3://<bucket>/bronze/positions/date=YYYY-MM-DD/`
- **Partitioning:** By date (drive `start_date`)
- **Description:** One-second position readings for completed drives only (where `drive_id` is not null)
- **Schema:**
  - `id` (bigint): Position ID
  - `drive_id` (bigint): Associated drive ID
  - `timestamp` (timestamp): Reading timestamp (ms precision)
  - `latitude`, `longitude` (double): GPS coordinates
  - `speed` (double): Speed in km/h
  - `power` (double): Power draw in kW
  - `odometer` (double): Odometer reading
  - `ideal_battery_range_km` (double): Ideal battery range
  - `battery_level` (int): Battery percentage
  - `outside_temp` (double): Outside temperature
  - `elevation` (double): Elevation in meters
  - `fan_status`, `driver_temp_setting`, `passenger_temp_setting` (int): Climate settings
  - `is_climate_on`, `is_rear_defroster_on`, `is_front_defroster_on` (boolean): Climate status

## Transformations

### From TeslaMate Schema to Bronze

1. **Energy Calculations (drives):**
   - Join `cars` table to get efficiency factor (kWh per km of rated range)
   - `kwh_used = (start_rated_range_km - end_rated_range_km) × car.efficiency`
   - `efficiency = kwh_used × 1000 / distance` (Wh/km)
   - If inputs are missing or distance is 0, values are NULL

2. **Battery Levels (drives):**
   - Join `positions` table via `start_position_id` and `end_position_id`
   - Extract `battery_level` from start and end positions

3. **Type Casting:**
   - All timestamps converted to millisecond precision (Athena-compatible)
   - Explicit PyArrow schema ensures Parquet types match Glue catalog
   - Nullable integers use `int32` (not `int64`)

4. **Positions Filtering:**
   - Only exports positions linked to completed drives (`drive_id IS NOT NULL`)
   - Partitioned by the drive's start date for efficient querying

## Execution

**Script:** `teslamate_platform/export/export_parquet.py`

**Schedule:** Nightly at 9 PM CT (via systemd timer `teslamate-export.timer`)

**Command:**
```bash
/opt/teslamate/venv/bin/python /opt/teslamate/export_parquet.py \
  --db-host localhost \
  --db-password "$POSTGRES_PASSWORD" \
  --s3-bucket <bucket-name> \
  --date YYYY-MM-DD
```

**Output:** Parquet files in `s3://<bucket>/bronze/` partitioned by date

## Data Quality

Bronze layer is a faithful copy of TeslaMate data with these guarantees:

- ✅ **Idempotent:** Safe to re-run for the same date
- ✅ **Type-safe:** Explicit Parquet schema matches Glue catalog
- ✅ **Athena-compatible:** Timestamps in milliseconds, not nanoseconds
- ✅ **Complete:** All source columns preserved
- ⚠️ **No validation:** Downstream silver layer applies quality checks

## Next Step

➡️ **Silver Layer** (`teslamate_platform/silver/`) applies quality checks and data cleaning
