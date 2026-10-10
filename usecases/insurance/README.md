# Insurance Use Case: Driving Risk Score

## Overview

This module implements a transparent insurance-style driving risk scoring system. Per-trip features are extracted from TeslaMate data and combined into a weighted 0-100 risk score with human-readable explanations.

**Status:** Skeleton only. No code yet.

## Planned Features

The scoring system will evaluate trips based on:

1. **Hard Braking** — Frequency and intensity of rapid deceleration events
2. **Hard Acceleration** — Frequency and intensity of rapid acceleration events  
3. **Speeding** — Time spent above speed limits (estimated from road type when GPS speed limit data is unavailable)
4. **Night Driving** — Proportion of driving between 10 PM and 5 AM local time
5. **Highway Share** — Proportion of miles driven on highways vs. residential/urban roads (proxy: sustained high speeds)

## Scoring Approach

The risk score will be a weighted combination of the above features:

```
risk_score = w1 * hard_braking_score 
           + w2 * hard_acceleration_score
           + w3 * speeding_score
           + w4 * night_driving_score
           + w5 * highway_score
```

Where weights (w1-w5) are assumption-based and sum to 100.

**Score range:** 0-100 (lower is better)
- **0-30:** Low risk (safe driver)
- **31-60:** Moderate risk (average driver)
- **61-100:** High risk (risky driving patterns)

Each score includes a breakdown showing which factors contributed most.

## Honest Limits

This is a demonstration portfolio project, not a production insurance model:

- **Single car:** Trained only on one driver's data from one vehicle
- **Assumption-based weights:** Feature weights are set by educated guesses, not optimized on crash/claim data
- **Not trained on crash data:** This model has never seen actual accident or insurance claim outcomes
- **No validation against real insurance risk:** Scores may not correlate with actual accident probability
- **Synthetic data for testing:** Sample trips are generated, not drawn from a large real-world dataset

Use this as a learning example of feature engineering, scoring systems, and MLOps patterns—not as a production risk assessment tool.

## Pipeline

When implemented, the SageMaker pipeline will follow the pattern from [sagemaker-mlops-pipeline-starter](https://github.com/saranreddy/sagemaker-mlops-pipeline-starter):

1. **Processing:** Feature extraction from raw drives in S3
2. **Scoring:** Apply weighted scoring logic (no training step; this is a rule-based system)
3. **Evaluation:** Compare scores across time periods and flag unusual patterns
4. **Registration:** Store scoring artifacts in Model Registry for versioning

## Module Structure

```
usecases/insurance/
├── README.md              (this file)
├── features/              Feature extraction from TeslaMate drives
│   └── README.md          (Feature definitions and extraction logic)
├── scoring/               Weighted scoring and explanation logic
│   └── README.md          (Scoring formula and weight definitions)
├── pipeline/              SageMaker pipeline orchestration
│   └── README.md          (Pipeline definition and execution)
└── synthetic/             Synthetic trip generation for testing
    └── README.md          (Synthetic data generation and labeling)
```

## Data Sources

This module reads from the shared platform data:

- **S3 raw drives:** `s3://<bucket>/raw/drives/date=YYYY-MM-DD/drives.parquet`
- **Glue table:** `teslamate_mlops_data.drives`

All outputs are written to:

- **S3 prefix:** `s3://<bucket>/usecases/insurance/`
- **Glue tables:** Prefixed with `insurance_*` (e.g., `insurance_trip_scores`)

## Module Isolation

Per the repository rules:

- This module **reads from** the shared platform data (drives, charges) but **does not modify** it
- This module **never reads from** other use case modules
- All outputs are scoped to the `usecases/insurance/` S3 prefix and Glue table namespace

## Next Steps

1. Implement feature extraction logic in `features/`
2. Define scoring weights and logic in `scoring/`
3. Create SageMaker pipeline in `pipeline/`
4. Generate labeled synthetic trips in `synthetic/` for testing before real data accumulates
