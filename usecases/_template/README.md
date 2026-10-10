# Use Case Module Template

This directory serves as a template for creating new use case modules.

## Module Structure

Every use case module should follow this standard layout:

```
usecases/<module-name>/
├── README.md              Overview, features, limits, data sources
├── features/              Feature extraction from platform data
│   └── README.md
├── pipeline/              SageMaker or other orchestration
│   └── README.md
└── (optional subdirs)     E.g., scoring/, synthetic/, notebooks/
```

## Module Rules

1. **Read from shared platform data only**
   - Use `s3://<bucket>/raw/drives/` and `s3://<bucket>/raw/charges/`
   - Use Glue tables `teslamate_mlops_data.drives` and `teslamate_mlops_data.charges`
   - Never modify platform data

2. **Never read from other use case modules**
   - Modules are isolated and independent
   - If you need data from another module, copy it to platform/ or refactor

3. **Own your S3 prefix**
   - All outputs go to `s3://<bucket>/usecases/<module-name>/`
   - Never write outside your module's namespace

4. **Prefix your Glue tables**
   - Name tables as `<module-name>_*` (e.g., `insurance_trip_scores`)
   - Prevents naming collisions across modules

5. **Label synthetic data**
   - If generating synthetic data, always set `is_synthetic=true` in metadata
   - Store in `usecases/<module-name>/synthetic/` to keep separate from real data

6. **Document honestly**
   - State limitations clearly in your README
   - Note assumptions, single-car constraints, or lack of real-world validation
   - Portfolio projects should be transparent about their scope

## README Template

Your use case README should include:

- **Overview** — What problem does this module solve?
- **Features** — What features or metrics are extracted?
- **Approach** — What model, scoring, or analysis method is used?
- **Honest Limits** — Single car? Assumptions? Not production-ready?
- **Data Sources** — What platform data does it read?
- **Outputs** — What S3 paths and Glue tables does it create?
- **Pipeline** — How is the workflow orchestrated?
- **Next Steps** — What's not implemented yet?

## Creating a New Module

1. Copy this template directory: `cp -r usecases/_template usecases/<your-module>`
2. Update the README with your use case details
3. Create subdirectories as needed (features/, pipeline/, etc.)
4. Implement your logic, following the module rules above
5. Update the root README to add your module to the module table

## Example Modules

- **insurance/** — Driving risk scoring with per-trip features and weighted score
- (Future: battery_health/, energy_efficiency/, etc.)
