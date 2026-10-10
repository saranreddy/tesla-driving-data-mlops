#!/usr/bin/env python3
"""Insurance use case: Extract trip features from silver layer.

Reads silver_drives and silver_positions (skipping flagged trips) and computes
insurance-relevant features for risk scoring.

Features:
- hard_brakes_per_100mi: Hard braking events per 100 miles
- hard_accels_per_100mi: Hard acceleration events per 100 miles
- pct_time_over_80mph: Percentage of time speeding >80 mph (~129 km/h)
- night_minutes: Minutes driven between 10 PM - 6 AM
- pct_highway: Estimated percentage of highway driving
- miles: Trip distance in miles
- duration_hours: Trip duration in hours
- avg_temp_f: Average temperature in Fahrenheit
- wh_per_km: Energy efficiency

Output: ins_trip_features table
"""

import argparse
import logging
import sys
from datetime import datetime, time, timedelta, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
KM_TO_MILES = 0.621371


def celsius_to_fahrenheit(c):
    """Convert Celsius to Fahrenheit."""
    return c * 9 / 5 + 32


HARD_BRAKE_THRESHOLD_MPS2 = -3.0  # m/s^2 (negative for braking)
HARD_ACCEL_THRESHOLD_MPS2 = 3.0  # m/s^2
SPEED_THRESHOLD_KMH = 129  # ~80 mph
HIGHWAY_SPEED_THRESHOLD_KMH = 90  # ~56 mph, sustained = highway
NIGHT_START = time(22, 0)  # 10 PM
NIGHT_END = time(6, 0)  # 6 AM


def is_night_time(dt: datetime) -> bool:
    """Check if datetime is during night hours (10 PM - 6 AM)."""
    t = dt.time()
    if NIGHT_START <= time(23, 59, 59):
        # Night spans midnight
        return t >= NIGHT_START or t < NIGHT_END
    else:
        return NIGHT_START <= t < NIGHT_END


def compute_hard_events(positions_df: pd.DataFrame, drive_id: int) -> tuple:
    """Compute hard braking and acceleration events for a drive.

    Returns:
        (hard_brakes_count, hard_accels_count)
    """
    drive_pos = positions_df[positions_df["drive_id"] == drive_id].sort_values(
        "timestamp"
    )

    if len(drive_pos) < 2:
        return 0, 0

    # Compute acceleration (change in speed / time delta)
    drive_pos = drive_pos.copy()
    drive_pos["speed_ms"] = drive_pos["speed"] / 3.6  # km/h to m/s
    drive_pos["time_delta"] = drive_pos["timestamp"].diff().dt.total_seconds()
    drive_pos["speed_delta"] = drive_pos["speed_ms"].diff()
    drive_pos["acceleration"] = drive_pos["speed_delta"] / drive_pos["time_delta"]

    # Count events
    hard_brakes = (drive_pos["acceleration"] <= HARD_BRAKE_THRESHOLD_MPS2).sum()
    hard_accels = (drive_pos["acceleration"] >= HARD_ACCEL_THRESHOLD_MPS2).sum()

    return hard_brakes, hard_accels


def compute_speeding_time(positions_df: pd.DataFrame, drive_id: int) -> float:
    """Compute percentage of time spent over 80 mph (~129 km/h).

    Returns:
        Percentage (0-100)
    """
    drive_pos = positions_df[positions_df["drive_id"] == drive_id]

    if drive_pos.empty:
        return 0.0

    speeding_count = (drive_pos["speed"] > SPEED_THRESHOLD_KMH).sum()
    total_count = len(drive_pos)

    return (speeding_count / total_count * 100.0) if total_count > 0 else 0.0


def compute_night_minutes(drive: pd.Series) -> float:
    """Compute minutes driven during night hours (10 PM - 6 AM)."""
    start = drive["start_date"]
    end = drive["end_date"]
    duration_min = drive["duration_min"]

    # Simple heuristic: if trip starts or ends during night, count all minutes
    # More sophisticated: iterate through time range (skipped for simplicity)
    if is_night_time(start) or is_night_time(end):
        return duration_min

    return 0.0


def compute_highway_pct(positions_df: pd.DataFrame, drive_id: int) -> float:
    """Estimate percentage of highway driving.

    Highway heuristic: sustained speed >90 km/h (~56 mph)

    Returns:
        Percentage (0-100)
    """
    drive_pos = positions_df[positions_df["drive_id"] == drive_id]

    if drive_pos.empty:
        return 0.0

    highway_count = (drive_pos["speed"] >= HIGHWAY_SPEED_THRESHOLD_KMH).sum()
    total_count = len(drive_pos)

    return (highway_count / total_count * 100.0) if total_count > 0 else 0.0


def extract_features(date_str: str, s3_bucket: str) -> pd.DataFrame:
    """Extract insurance features from silver layer.

    Args:
        date_str: Date to process (YYYY-MM-DD)
        s3_bucket: S3 bucket name

    Returns:
        DataFrame with trip features
    """
    drives_path = f"s3://{s3_bucket}/silver/drives/date={date_str}/drives.parquet"
    positions_path = (
        f"s3://{s3_bucket}/silver/positions/date={date_str}/positions.parquet"
    )

    try:
        drives_df = pd.read_parquet(drives_path)
        positions_df = pd.read_parquet(positions_path)
    except Exception as e:
        logger.warning(f"No silver data found for {date_str}: {e}")
        return pd.DataFrame()

    if drives_df.empty:
        logger.info(f"No drives to process for {date_str}")
        return pd.DataFrame()

    # Filter out flagged trips
    good_drives = drives_df[~drives_df["quality_flag"]].copy()
    logger.info(
        f"Processing {len(good_drives)}/{len(drives_df)} good drives "
        f"(skipped {len(drives_df) - len(good_drives)} flagged)"
    )

    if good_drives.empty:
        return pd.DataFrame()

    # Extract features for each drive
    features = []

    for _, drive in good_drives.iterrows():
        drive_id = drive["id"]

        # Compute event-based features
        hard_brakes, hard_accels = compute_hard_events(positions_df, drive_id)
        distance_mi = drive["distance"] * KM_TO_MILES

        # Normalize to per 100 miles
        hard_brakes_per_100mi = (
            (hard_brakes / distance_mi * 100.0) if distance_mi > 0 else 0.0
        )
        hard_accels_per_100mi = (
            (hard_accels / distance_mi * 100.0) if distance_mi > 0 else 0.0
        )

        # Other features
        pct_time_over_80mph = compute_speeding_time(positions_df, drive_id)
        night_minutes = compute_night_minutes(drive)
        pct_highway = compute_highway_pct(positions_df, drive_id)
        avg_temp_f = (
            celsius_to_fahrenheit(drive["outside_temp_avg"])
            if pd.notna(drive["outside_temp_avg"])
            else None
        )

        features.append(
            {
                "drive_id": drive_id,
                "date": drive["start_date"].date(),
                "hard_brakes_per_100mi": hard_brakes_per_100mi,
                "hard_accels_per_100mi": hard_accels_per_100mi,
                "pct_time_over_80mph": pct_time_over_80mph,
                "night_minutes": night_minutes,
                "pct_highway": pct_highway,
                "miles": distance_mi,
                "duration_hours": drive["duration_min"] / 60.0,
                "avg_temp_f": avg_temp_f,
                "wh_per_km": drive["efficiency"],
            }
        )

    features_df = pd.DataFrame(features)
    logger.info(f"Extracted features for {len(features_df)} drives")

    return features_df


def write_features(df: pd.DataFrame, date_str: str, s3_bucket: str):
    """Write insurance trip features to S3."""
    if df.empty:
        logger.info("No features to write")
        return

    s3_key = (
        f"usecases/insurance/gold/ins_trip_features/date={date_str}/features.parquet"
    )

    schema = pa.schema(
        [
            ("drive_id", pa.int64()),
            ("date", pa.date32()),
            ("hard_brakes_per_100mi", pa.float64()),
            ("hard_accels_per_100mi", pa.float64()),
            ("pct_time_over_80mph", pa.float64()),
            ("night_minutes", pa.float64()),
            ("pct_highway", pa.float64()),
            ("miles", pa.float64()),
            ("duration_hours", pa.float64()),
            ("avg_temp_f", pa.float64()),
            ("wh_per_km", pa.float64()),
        ]
    )

    table = pa.Table.from_pandas(df, schema=schema)
    pq.write_table(table, f"s3://{s3_bucket}/{s3_key}")

    logger.info(f"Wrote {len(df)} feature records to s3://{s3_bucket}/{s3_key}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract insurance features from silver layer"
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
        logger.info(f"Extracting insurance features for {date_str}")

        features_df = extract_features(date_str, args.s3_bucket)
        write_features(features_df, date_str, args.s3_bucket)

        logger.info("Feature extraction complete")

    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
