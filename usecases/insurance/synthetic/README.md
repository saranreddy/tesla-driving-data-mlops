# Synthetic Trip Generation

**Status:** Placeholder. No code yet.

## Purpose

Generate labeled synthetic driving trips for testing the scoring system before sufficient real data accumulates.

## Synthetic Data Requirements

1. **Labeled by risk level:** Generate low, medium, and high-risk trips with known characteristics
2. **Realistic distributions:** Speed, duration, and distance should match real Tesla driving patterns
3. **Clear separation:** Labeled as synthetic in metadata (never mixed with real data)
4. **Temporary:** Used only for initial testing and validation; replaced by real data over time

## Planned Trip Types

| Risk Level | Characteristics                                                   |
|------------|-------------------------------------------------------------------|
| Low        | No hard events, under speed limits, daytime, mixed road types     |
| Medium     | Occasional hard braking, minor speeding, evening driving          |
| High       | Frequent hard events, significant speeding, late-night highway    |

## Output

- **Target:** `s3://<bucket>/usecases/insurance/synthetic/trips/date=YYYY-MM-DD/synthetic_trips.parquet`
- **Metadata:** Labeled with `is_synthetic=true` and `risk_label=low|medium|high`

## Usage

1. Generate synthetic trips with known risk profiles
2. Run feature extraction and scoring pipeline on synthetic data
3. Verify that scores align with expected labels (low-risk trips → low scores, etc.)
4. Use as smoke test for pipeline before real data is sufficient

## Implementation Notes

- Use Python script with numpy/pandas to generate trips
- Match TeslaMate drives schema for compatibility
- Store in separate S3 prefix (`synthetic/`) to avoid contamination
- Never query synthetic and real data together without explicit filter
