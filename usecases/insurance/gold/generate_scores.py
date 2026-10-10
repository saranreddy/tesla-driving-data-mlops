#!/usr/bin/env python3
"""Insurance use case: Generate risk scores from trip features.

Reads ins_trip_features and computes a transparent 0-100 risk score with
configurable weights and normalization parameters.

Score components:
- Hard braking penalty
- Hard acceleration penalty
- Speeding penalty
- Night driving penalty
- Highway driving bonus

Output: ins_trip_scores table with score and top reasons
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = None) -> dict:
    """Load scoring configuration."""
    if config_path is None:
        # Default to config file in same directory
        config_path = Path(__file__).parent / "scoring_config.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Validate weights sum to ~1.0
    weights = config["weights"]
    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        logger.warning(f"Weights sum to {weight_sum:.3f}, not 1.0")

    return config


def normalize_value(value: float, max_value: float) -> float:
    """Normalize a value to 0-100 scale."""
    if pd.isna(value):
        return 0.0
    return min(value / max_value * 100.0, 100.0)


def compute_score(row: pd.Series, config: dict) -> tuple:
    """Compute insurance risk score for a trip.

    Returns:
        (score, top_reasons)
    """
    weights = config["weights"]
    norm = config["normalization"]

    # Normalize each component to 0-100
    hard_brakes_norm = normalize_value(
        row["hard_brakes_per_100mi"], norm["hard_brakes_per_100mi"]["max_value"]
    )

    hard_accels_norm = normalize_value(
        row["hard_accels_per_100mi"], norm["hard_accels_per_100mi"]["max_value"]
    )

    speeding_norm = normalize_value(
        row["pct_time_over_80mph"], norm["pct_time_over_80mph"]["max_value"]
    )

    # Night driving normalized per hour
    night_per_hour = (
        row["night_minutes"] / row["duration_hours"] if row["duration_hours"] > 0 else 0
    )
    night_norm = normalize_value(night_per_hour, norm["night_minutes"]["max_per_hour"])

    # Highway bonus (more highway = lower score)
    highway_delta = row["pct_highway"] - norm["pct_highway"]["baseline"]
    highway_bonus = -highway_delta if highway_delta > 0 else 0  # Only bonus, no penalty

    # Weighted score
    score = (
        hard_brakes_norm * weights["hard_brakes"]
        + hard_accels_norm * weights["hard_accels"]
        + speeding_norm * weights["speeding"]
        + night_norm * weights["night_driving"]
        + highway_bonus * weights["highway_bonus"]
    )

    # Clamp to 0-100
    score = max(0.0, min(100.0, score))

    # Identify top contributing factors
    components = [
        ("hard_braking", hard_brakes_norm * weights["hard_brakes"]),
        ("hard_acceleration", hard_accels_norm * weights["hard_accels"]),
        ("speeding", speeding_norm * weights["speeding"]),
        ("night_driving", night_norm * weights["night_driving"]),
    ]

    # Sort by contribution (descending)
    components_sorted = sorted(components, key=lambda x: x[1], reverse=True)

    # Top 3 reasons (if contribution > 5 points)
    top_reasons = [comp[0] for comp in components_sorted[:3] if comp[1] > 5.0]

    return score, ",".join(top_reasons) if top_reasons else "safe_driver"


def generate_scores(date_str: str, s3_bucket: str, config: dict) -> pd.DataFrame:
    """Generate insurance scores from features.

    Args:
        date_str: Date to process (YYYY-MM-DD)
        s3_bucket: S3 bucket name
        config: Scoring configuration

    Returns:
        DataFrame with scores
    """
    features_path = (
        f"s3://{s3_bucket}/usecases/insurance/gold/"
        f"ins_trip_features/date={date_str}/features.parquet"
    )

    try:
        features_df = pd.read_parquet(features_path)
    except Exception as e:
        logger.warning(f"No features found for {date_str}: {e}")
        return pd.DataFrame()

    if features_df.empty:
        logger.info(f"No features to score for {date_str}")
        return features_df

    # Compute scores
    scores = []

    for _, row in features_df.iterrows():
        score, reasons = compute_score(row, config)

        scores.append(
            {
                "drive_id": row["drive_id"],
                "date": row["date"],
                "risk_score": score,
                "score_category": categorize_score(score),
                "top_risk_factors": reasons,
            }
        )

    scores_df = pd.DataFrame(scores)

    avg_score = scores_df["risk_score"].mean()
    logger.info(
        f"Generated scores for {len(scores_df)} trips, " f"avg score: {avg_score:.1f}"
    )

    return scores_df


def categorize_score(score: float) -> str:
    """Categorize score into risk buckets."""
    if score <= 20:
        return "excellent"
    elif score <= 40:
        return "good"
    elif score <= 60:
        return "average"
    elif score <= 80:
        return "below_average"
    else:
        return "poor"


def write_scores(df: pd.DataFrame, date_str: str, s3_bucket: str):
    """Write insurance scores to S3."""
    if df.empty:
        logger.info("No scores to write")
        return

    s3_key = f"usecases/insurance/gold/ins_trip_scores/date={date_str}/scores.parquet"

    schema = pa.schema(
        [
            ("drive_id", pa.int64()),
            ("date", pa.date32()),
            ("risk_score", pa.float64()),
            ("score_category", pa.string()),
            ("top_risk_factors", pa.string()),
        ]
    )

    table = pa.Table.from_pandas(df, schema=schema)
    pq.write_table(table, f"s3://{s3_bucket}/{s3_key}")

    logger.info(f"Wrote {len(df)} scores to s3://{s3_bucket}/{s3_key}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate insurance risk scores from trip features"
    )
    parser.add_argument(
        "--date", help="Date to process (YYYY-MM-DD), defaults to yesterday"
    )
    parser.add_argument("--s3-bucket", required=True, help="S3 bucket name")
    parser.add_argument(
        "--config", help="Path to scoring config YAML (defaults to scoring_config.yaml)"
    )

    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    try:
        logger.info("Loading scoring configuration")
        config = load_config(args.config)

        logger.info(f"Generating insurance scores for {date_str}")
        scores_df = generate_scores(date_str, args.s3_bucket, config)
        write_scores(scores_df, date_str, args.s3_bucket)

        logger.info("Score generation complete")

    except Exception as e:
        logger.error(f"Score generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
