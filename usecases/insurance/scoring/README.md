# Scoring Logic

**Status:** Placeholder. No code yet.

## Purpose

Apply weighted scoring to extracted features and produce a 0-100 risk score with explanations.

## Scoring Formula

```
risk_score = (w1 * hard_braking_score 
            + w2 * hard_acceleration_score
            + w3 * speeding_score
            + w4 * night_driving_score
            + w5 * highway_score)
```

## Weight Definitions (Assumption-Based)

| Feature                 | Weight | Rationale                                      |
|-------------------------|--------|------------------------------------------------|
| Hard Braking            | 25%    | Strong indicator of reactive/aggressive driving|
| Hard Acceleration       | 20%    | Indicates aggressive driving patterns          |
| Speeding                | 30%    | Direct correlation with crash severity         |
| Night Driving           | 15%    | Higher accident rates at night                 |
| Highway Driving         | 10%    | Lower risk per mile than urban driving         |

**Total:** 100%

These weights are **not** trained on real insurance or crash data. They are educated guesses for demonstration purposes.

## Score Interpretation

- **0-30:** Low risk (safe driver)
- **31-60:** Moderate risk (average driver)
- **61-100:** High risk (risky driving patterns)

## Explanation Output

Each score includes:
- Overall risk score (0-100)
- Per-feature sub-scores (0-100)
- Top 3 contributing factors with readable descriptions

Example:
```json
{
  "trip_id": 12345,
  "risk_score": 42,
  "breakdown": {
    "hard_braking": 15,
    "hard_acceleration": 10,
    "speeding": 35,
    "night_driving": 5,
    "highway_share": -15
  },
  "top_factors": [
    "Speeding: 12 minutes over estimated limits",
    "Hard braking: 3 events",
    "Night driving: 40% of trip after 10 PM"
  ]
}
```

## Implementation Notes

- Use SageMaker Processing or Lambda for batch scoring
- Store scored trips in `s3://<bucket>/usecases/insurance/scores/date=YYYY-MM-DD/scores.parquet`
- Create Glue table `insurance_trip_scores` for Athena queries
