# 🥇 Gold Layer — Insurance Risk Scoring

## Overview

The gold layer contains business-specific, curated data ready for analytics and ML. The **insurance use case** extracts driving behavior features and generates transparent risk scores from silver layer data.

**Input:** Silver layer (quality-checked data)  
**Output:** `s3://<bucket>/usecases/insurance/gold/` → Glue database `teslamate_insurance`

## Architecture

```
Silver Layer (good trips only)
  ↓
Feature Extraction (extract_features.py)
  ↓
ins_trip_features
  ↓
Risk Scoring (generate_scores.py)
  ↓
ins_trip_scores
```

## Output Tables

### ins_trip_features
- **Location:** `s3://<bucket>/usecases/insurance/gold/ins_trip_features/date=YYYY-MM-DD/`
- **Description:** Driving behavior features per trip
- **Schema:**
  - `drive_id` (bigint): Trip ID (links to silver_drives)
  - `date` (date): Trip date
  - `hard_brakes_per_100mi` (double): Hard braking events per 100 miles
  - `hard_accels_per_100mi` (double): Hard acceleration events per 100 miles
  - `pct_time_over_80mph` (double): % of time speeding >80 mph (~129 km/h)
  - `night_minutes` (double): Minutes driven 10 PM - 6 AM
  - `pct_highway` (double): % highway driving (speed >90 km/h sustained)
  - `miles` (double): Distance in miles
  - `duration_hours` (double): Trip duration in hours
  - `avg_temp_f` (double): Average temperature in Fahrenheit
  - `wh_per_km` (double): Energy efficiency (Wh/km)

### ins_trip_scores
- **Location:** `s3://<bucket>/usecases/insurance/gold/ins_trip_scores/date=YYYY-MM-DD/`
- **Description:** Insurance risk scores (0-100, lower = safer)
- **Schema:**
  - `drive_id` (bigint): Trip ID
  - `date` (date): Trip date
  - `risk_score` (double): Composite risk score (0-100)
  - `score_category` (string): `excellent` / `good` / `average` / `below_average` / `poor`
  - `top_risk_factors` (string): Comma-separated top contributing factors

## Feature Definitions

### Hard Braking / Acceleration
- **Detection:** Acceleration/deceleration exceeds ±3.0 m/s²
- **Computation:** Count events, normalize to per-100-miles
- **Data Source:** `silver_positions` (1-second readings)

### Speeding
- **Threshold:** >80 mph (~129 km/h)
- **Computation:** % of position readings above threshold
- **Insurance rationale:** High-speed driving correlates with accident risk

### Night Driving
- **Definition:** 10 PM - 6 AM local time
- **Computation:** Minutes driven during night hours
- **Insurance rationale:** Fatigue and visibility risks

### Highway Driving
- **Heuristic:** Sustained speed >90 km/h (~56 mph)
- **Computation:** % of position readings on highway
- **Insurance rationale:** Highway miles are *safer* (bonus, not penalty)

### Energy Efficiency
- **Metric:** Wh/km from silver_drives
- **Use:** Proxy for driving smoothness (informational, not scored)

## Risk Scoring Model

### Weights (`scoring_config.yaml`)

| Factor | Weight | Rationale |
|--------|--------|-----------|
| Hard braking | 25% | Indicates aggressive/reactive driving |
| Hard acceleration | 20% | Indicates aggressive driving |
| Speeding | 30% | Highest accident correlation |
| Night driving | 15% | Fatigue/visibility risks |
| Highway bonus | -10% | Highway miles are statistically safer |

**Weights sum to 100%** and are fully transparent and configurable.

### Normalization

Raw features are normalized to 0-100 scale:

- **Hard events:** Max at 20 events per 100 mi
- **Speeding:** Max at 50% time over limit
- **Night driving:** Max at 30 min/hour
- **Highway:** Bonus above 50% baseline

### Score Categories

| Score | Category | Description |
|-------|----------|-------------|
| 0-20 | Excellent | Very safe driver |
| 21-40 | Good | Safe driver |
| 41-60 | Average | Typical driver |
| 61-80 | Below average | Risky behaviors present |
| 81-100 | Poor | Very risky driver |

### Top Risk Factors

Identifies up to 3 factors contributing >5 points to the score:
- `hard_braking`
- `hard_acceleration`
- `speeding`
- `night_driving`
- `safe_driver` (if score is low and no major factor)

## Execution

### Feature Extraction
**Script:** `usecases/insurance/gold/extract_features.py`  
**Schedule:** Nightly after silver (9:10 PM CT)

```bash
/opt/teslamate/venv/bin/python /opt/teslamate/insurance/extract_features.py \
  --s3-bucket <bucket-name> \
  --date YYYY-MM-DD
```

### Score Generation
**Script:** `usecases/insurance/gold/generate_scores.py`  
**Schedule:** Nightly after features (9:15 PM CT)

```bash
/opt/teslamate/venv/bin/python /opt/teslamate/insurance/generate_scores.py \
  --s3-bucket <bucket-name> \
  --date YYYY-MM-DD \
  --config /opt/teslamate/insurance/scoring_config.yaml
```

## Data Transformations

### From Silver to Gold

1. **Filter flagged trips:**
   - Only processes `silver_drives` where `quality_flag = false`
   - Skips trips with data quality issues

2. **Unit conversions:**
   - km → miles (×0.621371)
   - Celsius → Fahrenheit (×9/5 + 32)
   - m/s² thresholds for acceleration

3. **Aggregations:**
   - Count hard events across 1-second readings
   - Compute time-based percentages
   - Normalize to standard trip length (per 100 mi)

4. **Scoring:**
   - Weighted combination of normalized factors
   - Clamped to 0-100 range
   - Top contributors identified

## Querying Gold Data

### Trip Features
```sql
SELECT drive_id, miles, hard_brakes_per_100mi, pct_time_over_80mph
FROM teslamate_insurance.ins_trip_features
WHERE date = '2026-10-09'
ORDER BY hard_brakes_per_100mi DESC
```

### Risk Distribution
```sql
SELECT score_category, COUNT(*) as trip_count, AVG(risk_score) as avg_score
FROM teslamate_insurance.ins_trip_scores
WHERE date >= '2026-10-01' AND date <= '2026-10-31'
GROUP BY score_category
ORDER BY avg_score
```

### Risky Trips
```sql
SELECT s.drive_id, s.risk_score, s.top_risk_factors,
       f.hard_brakes_per_100mi, f.pct_time_over_80mph
FROM teslamate_insurance.ins_trip_scores s
JOIN teslamate_insurance.ins_trip_features f ON s.drive_id = f.drive_id
WHERE s.date = '2026-10-09'
  AND s.risk_score > 60
ORDER BY s.risk_score DESC
```

## Assumptions & Limitations

### Documented Assumptions
1. **Hard event thresholds (±3.0 m/s²):** Based on NHTSA research; configurable in code
2. **Speeding threshold (80 mph):** Common insurance policy limit
3. **Night hours (10 PM - 6 AM):** Standard definition; time zone is UTC
4. **Highway heuristic (>90 km/h):** Approximation; no road type data available
5. **Scoring weights:** Derived from insurance industry benchmarks; fully transparent

### Known Limitations
- **No road type data:** Highway driving inferred from speed
- **No weather data:** Temperature only; rain/snow unknown
- **No traffic data:** Cannot distinguish congestion from voluntary slowing
- **GPS accuracy:** Hard events may include false positives from GPS jitter
- **Single vehicle:** Multi-vehicle fleet behavior not analyzed

### Future Enhancements
- [ ] Weather API integration (rain/snow penalties)
- [ ] Road type from OSM (true highway vs surface streets)
- [ ] Traffic-adjusted scoring (don't penalize congestion slowdowns)
- [ ] Comparative scoring (percentile vs fleet average)
- [ ] Monthly/annual aggregates (trend analysis)

## Testing

See `tests/test_gold/` for:
- Feature extraction with synthetic trips
- Scoring logic with known inputs
- Edge cases (zero distance, missing positions, etc.)
- Real trip fixture (40.4 km Model S 100D trip)

## Next Steps

- 📊 **Visualization:** Grafana dashboards for risk trends
- 🤖 **ML Model:** Predict accident likelihood from features
- 💰 **Premium Calculation:** Map risk scores to insurance rates
- 📱 **Driver Feedback:** Real-time alerts for risky behavior
