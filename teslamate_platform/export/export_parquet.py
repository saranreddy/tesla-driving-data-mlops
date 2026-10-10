#!/usr/bin/env python3
"""Export TeslaMate data to Parquet format in S3.

Exports drives and charges from the TeslaMate PostgreSQL database to Parquet files
in S3, partitioned by date. Idempotent: safe to run multiple times for the same date.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import psycopg2
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_db_connection(
    host: str = "localhost",
    port: int = 5432,
    user: str = "teslamate",
    password: Optional[str] = None,
    dbname: str = "teslamate",
) -> psycopg2.extensions.connection:
    """Connect to TeslaMate PostgreSQL database."""
    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
    )


def export_drives(
    conn: psycopg2.extensions.connection,
    date_str: str,
    s3_bucket: str,
    s3_prefix: str = "raw/drives",
) -> int:
    """Export drives for a given date to S3 Parquet.

    Args:
        conn: PostgreSQL database connection
        date_str: Date to export in YYYY-MM-DD format
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for drives data

    Returns:
        Number of drives exported
    """
    query = """
    SELECT
        d.id,
        d.start_date,
        d.end_date,
        sa.display_name as start_address,
        ea.display_name as end_address,
        d.distance,
        EXTRACT(EPOCH FROM (d.end_date - d.start_date)) / 60 as duration_min,
        d.start_km,
        d.end_km,
        CASE
            WHEN d.start_rated_range_km IS NOT NULL
                AND d.end_rated_range_km IS NOT NULL
                AND c.efficiency IS NOT NULL
            THEN (d.start_rated_range_km - d.end_rated_range_km) * c.efficiency
            ELSE NULL
        END as kwh_used,
        sp.battery_level as start_battery_level,
        ep.battery_level as end_battery_level,
        d.outside_temp_avg,
        d.speed_max,
        CASE
            WHEN d.distance > 0
                AND d.start_rated_range_km IS NOT NULL
                AND d.end_rated_range_km IS NOT NULL
                AND c.efficiency IS NOT NULL
            THEN ((d.start_rated_range_km - d.end_rated_range_km)
                  * c.efficiency * 1000) / d.distance
            ELSE NULL
        END as efficiency
    FROM drives d
    LEFT JOIN addresses sa ON d.start_address_id = sa.id
    LEFT JOIN addresses ea ON d.end_address_id = ea.id
    LEFT JOIN positions sp ON d.start_position_id = sp.id
    LEFT JOIN positions ep ON d.end_position_id = ep.id
    LEFT JOIN cars c ON d.car_id = c.id
    WHERE DATE(d.start_date) = %s
    ORDER BY d.start_date
    """

    df = pd.read_sql_query(query, conn, params=(date_str,))

    if df.empty:
        logger.info(f"No drives found for {date_str}")
        return 0

    # Cast to exact Glue schema types
    # bigint: id
    df["id"] = df["id"].astype("int64")

    # timestamp: start_date, end_date (convert to ms precision for Athena)
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.floor("ms")
    df["end_date"] = pd.to_datetime(df["end_date"]).dt.floor("ms")

    # string: start_address, end_address
    df["start_address"] = df["start_address"].astype("string")
    df["end_address"] = df["end_address"].astype("string")

    # double: distance, duration_min, start_km, end_km, kwh_used,
    #         outside_temp_avg, speed_max, efficiency
    for col in [
        "distance",
        "duration_min",
        "start_km",
        "end_km",
        "kwh_used",
        "outside_temp_avg",
        "speed_max",
        "efficiency",
    ]:
        df[col] = df[col].astype("float64")

    # int: start_battery_level, end_battery_level (nullable)
    df["start_battery_level"] = df["start_battery_level"].astype("Int32")
    df["end_battery_level"] = df["end_battery_level"].astype("Int32")

    s3_key = f"{s3_prefix}/date={date_str}/drives.parquet"

    # Write with explicit schema to ensure int32 for nullable ints
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
        ]
    )

    table = pa.Table.from_pandas(df, schema=schema)
    pq.write_table(table, f"s3://{s3_bucket}/{s3_key}")

    logger.info(f"Exported {len(df)} drives to s3://{s3_bucket}/{s3_key}")
    return len(df)


def export_charges(
    conn: psycopg2.extensions.connection,
    date_str: str,
    s3_bucket: str,
    s3_prefix: str = "raw/charges",
) -> int:
    """Export charges for a given date to S3 Parquet.

    Args:
        conn: PostgreSQL database connection
        date_str: Date to export in YYYY-MM-DD format
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for charges data

    Returns:
        Number of charges exported
    """
    query = """
    SELECT
        c.id,
        c.start_date,
        c.end_date,
        a.display_name as address,
        c.charge_energy_added,
        c.start_battery_level,
        c.end_battery_level,
        EXTRACT(EPOCH FROM (c.end_date - c.start_date)) / 60 as duration_min,
        c.cost
    FROM charging_processes c
    LEFT JOIN addresses a ON c.address_id = a.id
    WHERE DATE(c.start_date) = %s
    ORDER BY c.start_date
    """

    df = pd.read_sql_query(query, conn, params=(date_str,))

    if df.empty:
        logger.info(f"No charges found for {date_str}")
        return 0

    # Cast to exact Glue schema types
    # bigint: id
    df["id"] = df["id"].astype("int64")

    # timestamp: start_date, end_date (convert to ms precision for Athena)
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.floor("ms")
    df["end_date"] = pd.to_datetime(df["end_date"]).dt.floor("ms")

    # string: address
    df["address"] = df["address"].astype("string")

    # double: charge_energy_added, duration_min, cost
    df["charge_energy_added"] = df["charge_energy_added"].astype("float64")
    df["duration_min"] = df["duration_min"].astype("float64")
    df["cost"] = df["cost"].astype("float64")

    # int: start_battery_level, end_battery_level (nullable)
    df["start_battery_level"] = df["start_battery_level"].astype("Int32")
    df["end_battery_level"] = df["end_battery_level"].astype("Int32")

    s3_key = f"{s3_prefix}/date={date_str}/charges.parquet"

    # Write with explicit schema to ensure int32 for nullable ints
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("start_date", pa.timestamp("ms")),
            ("end_date", pa.timestamp("ms")),
            ("address", pa.string()),
            ("charge_energy_added", pa.float64()),
            ("start_battery_level", pa.int32()),
            ("end_battery_level", pa.int32()),
            ("duration_min", pa.float64()),
            ("cost", pa.float64()),
        ]
    )

    table = pa.Table.from_pandas(df, schema=schema)
    pq.write_table(table, f"s3://{s3_bucket}/{s3_key}")

    logger.info(f"Exported {len(df)} charges to s3://{s3_bucket}/{s3_key}")
    return len(df)


def main():
    parser = argparse.ArgumentParser(
        description="Export TeslaMate data to Parquet in S3"
    )
    parser.add_argument(
        "--date", help="Date to export (YYYY-MM-DD), defaults to yesterday"
    )
    parser.add_argument("--db-host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--db-port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--db-user", default="teslamate", help="PostgreSQL user")
    parser.add_argument(
        "--db-password", help="PostgreSQL password (or set POSTGRES_PASSWORD env var)"
    )
    parser.add_argument(
        "--db-name", default="teslamate", help="PostgreSQL database name"
    )
    parser.add_argument("--s3-bucket", required=True, help="S3 bucket for exports")

    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    db_password = args.db_password or os.environ.get("POSTGRES_PASSWORD")
    if not db_password:
        logger.error(
            "Database password required (--db-password or POSTGRES_PASSWORD env var)"
        )
        sys.exit(1)

    try:
        logger.info(f"Connecting to database at {args.db_host}:{args.db_port}")
        conn = get_db_connection(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            password=db_password,
            dbname=args.db_name,
        )

        logger.info(f"Exporting data for {date_str} to s3://{args.s3_bucket}")

        drives_count = export_drives(conn, date_str, args.s3_bucket)
        charges_count = export_charges(conn, date_str, args.s3_bucket)

        logger.info(f"Export complete: {drives_count} drives, {charges_count} charges")

        conn.close()

    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
