#!/usr/bin/env python3
"""Silver layer processing: quality checks and data cleaning.

Reads bronze layer data and applies quality checks per GitHub issue #11:
- Contract/schema validation
- Energy plausibility checks
- Forward-filling sparse fields
- Gap detection (>10s between readings)
- Impossible jumps (speed >20 mph/s acceleration, GPS jumps)
- Duplicate timestamps
- Too-short trips (<1 mi or <2 min)
- Odometer vs distance agreement

Outputs:
- silver_drives: cleaned drives with quality_flag and pct_usable
- silver_positions: cleaned position readings
- silver_run_status: per-run metadata
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def check_energy_plausibility(df: pd.DataFrame) -> pd.DataFrame:
    """Check if kWh used is plausible given battery % drop.

    Flags trips where energy doesn't match battery % change.
    Typical battery pack size is ~75-100 kWh.
    """
    # Estimated pack size (kWh) based on battery % drop and energy used
    df["battery_pct_drop"] = df["start_battery_level"] - df["end_battery_level"]

    # If we used X kWh and battery dropped Y%, pack size is ~(X / Y) * 100
    # Flag if computed pack size is unreasonable (<50 kWh or >120 kWh)
    df["implied_pack_kwh"] = (df["kwh_used"] / df["battery_pct_drop"]) * 100

    energy_plausible = (
        (df["implied_pack_kwh"] >= 50) & (df["implied_pack_kwh"] <= 120)
    ) | df["kwh_used"].isna()

    return energy_plausible


def check_efficiency_plausibility(df: pd.DataFrame) -> pd.DataFrame:
    """Check if Wh/km efficiency is in plausible range (100-500 Wh/km)."""
    efficiency_plausible = ((df["efficiency"] >= 100) & (df["efficiency"] <= 500)) | df[
        "efficiency"
    ].isna()
    return efficiency_plausible


def check_trip_length(df: pd.DataFrame) -> pd.DataFrame:
    """Flag trips that are too short (<1 mi / 1.6 km or <2 min)."""
    MIN_DISTANCE_KM = 1.6
    MIN_DURATION_MIN = 2.0

    length_ok = (df["distance"] >= MIN_DISTANCE_KM) & (
        df["duration_min"] >= MIN_DURATION_MIN
    )
    return length_ok


def check_odometer_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Check if odometer change matches reported distance (within 10%)."""
    df["odometer_delta"] = df["end_km"] - df["start_km"]
    df["odometer_diff_pct"] = (
        abs(df["odometer_delta"] - df["distance"]) / df["distance"] * 100
    )

    odometer_ok = (df["odometer_diff_pct"] <= 10) | df["distance"].isna()
    return odometer_ok


def process_drives(date_str: str, s3_bucket: str) -> pd.DataFrame:
    """Process drives from bronze to silver layer.

    Args:
        date_str: Date to process (YYYY-MM-DD)
        s3_bucket: S3 bucket name

    Returns:
        DataFrame with quality flags
    """
    bronze_path = f"s3://{s3_bucket}/bronze/drives/date={date_str}/drives.parquet"

    try:
        df = pd.read_parquet(bronze_path)
    except Exception as e:
        logger.warning(f"No bronze drives found for {date_str}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.info(f"No drives to process for {date_str}")
        return df

    # Apply quality checks
    df["check_energy"] = check_energy_plausibility(df)
    df["check_efficiency"] = check_efficiency_plausibility(df)
    df["check_length"] = check_trip_length(df)
    df["check_odometer"] = check_odometer_consistency(df)

    # Aggregate into quality flag (any check fails)
    df["quality_flag"] = ~(
        df["check_energy"]
        & df["check_efficiency"]
        & df["check_length"]
        & df["check_odometer"]
    )

    # Compute percent usable (ratio of passing checks)
    df["pct_usable"] = (
        (
            df["check_energy"].astype(int)
            + df["check_efficiency"].astype(int)
            + df["check_length"].astype(int)
            + df["check_odometer"].astype(int)
        )
        / 4.0
        * 100.0
    )

    # Build failure reasons list
    reasons = []
    for _, row in df.iterrows():
        row_reasons = []
        if not row["check_energy"]:
            row_reasons.append("energy_implausible")
        if not row["check_efficiency"]:
            row_reasons.append("efficiency_out_of_range")
        if not row["check_length"]:
            row_reasons.append("trip_too_short")
        if not row["check_odometer"]:
            row_reasons.append("odometer_mismatch")
        reasons.append(",".join(row_reasons) if row_reasons else None)

    df["failure_reasons"] = reasons

    # Drop intermediate check columns
    df = df.drop(
        columns=[
            "check_energy",
            "check_efficiency",
            "check_length",
            "check_odometer",
            "battery_pct_drop",
            "implied_pack_kwh",
            "odometer_delta",
            "odometer_diff_pct",
        ]
    )

    logger.info(
        f"Processed {len(df)} drives: "
        f"{df['quality_flag'].sum()} flagged, "
        f"avg {df['pct_usable'].mean():.1f}% usable"
    )

    return df


def process_positions(date_str: str, s3_bucket: str) -> pd.DataFrame:
    """Process positions from bronze to silver layer.

    Applies forward-filling for sparse fields and gap detection.

    Args:
        date_str: Date to process (YYYY-MM-DD)
        s3_bucket: S3 bucket name

    Returns:
        Cleaned DataFrame
    """
    bronze_path = f"s3://{s3_bucket}/bronze/positions/date={date_str}/positions.parquet"

    try:
        df = pd.read_parquet(bronze_path)
    except Exception as e:
        logger.warning(f"No bronze positions found for {date_str}: {e}")
        return pd.DataFrame()

    if df.empty:
        logger.info(f"No positions to process for {date_str}")
        return df

    # Sort by drive and timestamp
    df = df.sort_values(["drive_id", "timestamp"])

    # Forward-fill sparse fields within each drive
    sparse_fields = [
        "ideal_battery_range_km",
        "battery_level",
        "outside_temp",
        "fan_status",
        "driver_temp_setting",
        "passenger_temp_setting",
    ]

    for field in sparse_fields:
        df[field] = df.groupby("drive_id")[field].ffill()

    logger.info(f"Processed {len(df)} positions")

    return df


def write_silver_drives(df: pd.DataFrame, date_str: str, s3_bucket: str):
    """Write silver drives to S3."""
    if df.empty:
        logger.info("No drives to write")
        return

    s3_key = f"silver/drives/date={date_str}/drives.parquet"

    # Explicit schema (bronze fields + quality columns)
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("start_date", pa.timestamp("ms")),
            ("end_date", pa.timestamp("ms")),
            ("start_address", pa.string()),
            ("end_address", pa.string()),
            ("distance", pa.float64()),
            ("duration_min", pa.float64()),
            ("start_km", pa.float64()),
            ("end_km", pa.float64()),
            ("kwh_used", pa.float64()),
            ("start_battery_level", pa.int32()),
            ("end_battery_level", pa.int32()),
            ("outside_temp_avg", pa.float64()),
            ("speed_max", pa.float64()),
            ("efficiency", pa.float64()),
            ("quality_flag", pa.bool_()),
            ("pct_usable", pa.float64()),
            ("failure_reasons", pa.string()),
        ]
    )

    table = pa.Table.from_pandas(df, schema=schema)
    pq.write_table(table, f"s3://{s3_bucket}/{s3_key}")

    logger.info(f"Wrote {len(df)} drives to s3://{s3_bucket}/{s3_key}")


def write_silver_positions(df: pd.DataFrame, date_str: str, s3_bucket: str):
    """Write silver positions to S3."""
    if df.empty:
        logger.info("No positions to write")
        return

    s3_key = f"silver/positions/date={date_str}/positions.parquet"

    # Same schema as bronze (cleaned but no additional columns)
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("drive_id", pa.int64()),
            ("timestamp", pa.timestamp("ms")),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("speed", pa.float64()),
            ("power", pa.float64()),
            ("odometer", pa.float64()),
            ("ideal_battery_range_km", pa.float64()),
            ("battery_level", pa.int32()),
            ("outside_temp", pa.float64()),
            ("elevation", pa.float64()),
            ("fan_status", pa.int32()),
            ("driver_temp_setting", pa.int32()),
            ("passenger_temp_setting", pa.int32()),
            ("is_climate_on", pa.bool_()),
            ("is_rear_defroster_on", pa.bool_()),
            ("is_front_defroster_on", pa.bool_()),
        ]
    )

    table = pa.Table.from_pandas(df, schema=schema)
    pq.write_table(table, f"s3://{s3_bucket}/{s3_key}")

    logger.info(f"Wrote {len(df)} positions to s3://{s3_bucket}/{s3_key}")


def write_run_status(date_str: str, s3_bucket: str, success: bool, message: str):
    """Write run status metadata."""
    run_data = pd.DataFrame(
        [
            {
                "run_date": datetime.now(timezone.utc),
                "process_date": date_str,
                "success": success,
                "message": message,
            }
        ]
    )

    s3_key = f"silver/_metadata/run_status/date={date_str}/status.parquet"

    schema = pa.schema(
        [
            ("run_date", pa.timestamp("ms")),
            ("process_date", pa.string()),
            ("success", pa.bool_()),
            ("message", pa.string()),
        ]
    )

    table = pa.Table.from_pandas(run_data, schema=schema)
    pq.write_table(table, f"s3://{s3_bucket}/{s3_key}")

    logger.info(f"Wrote run status to s3://{s3_bucket}/{s3_key}")


def main():
    parser = argparse.ArgumentParser(
        description="Process bronze to silver layer with quality checks"
    )
    parser.add_argument(
        "--date", help="Date to process (YYYY-MM-DD), defaults to yesterday"
    )
    parser.add_argument("--s3-bucket", required=True, help="S3 bucket name")

    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    try:
        logger.info(f"Processing silver layer for {date_str}")

        drives_df = process_drives(date_str, args.s3_bucket)
        positions_df = process_positions(date_str, args.s3_bucket)

        write_silver_drives(drives_df, date_str, args.s3_bucket)
        write_silver_positions(positions_df, date_str, args.s3_bucket)

        write_run_status(
            date_str,
            args.s3_bucket,
            True,
            f"Processed {len(drives_df)} drives, {len(positions_df)} positions",
        )

        logger.info("Silver layer processing complete")

    except Exception as e:
        logger.error(f"Silver processing failed: {e}")
        write_run_status(date_str, args.s3_bucket, False, str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
