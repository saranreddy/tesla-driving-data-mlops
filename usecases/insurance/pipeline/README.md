# SageMaker Pipeline

**Status:** Placeholder. No code yet.

## Purpose

Orchestrate the end-to-end feature extraction, scoring, and evaluation workflow using SageMaker Pipelines.

## Pipeline Steps

1. **FeatureExtraction** (Processing)
   - Read raw drives from S3
   - Extract risk features
   - Write to `usecases/insurance/features/`

2. **Scoring** (Processing)
   - Read extracted features
   - Apply weighted scoring logic
   - Generate explanations
   - Write to `usecases/insurance/scores/`

3. **Evaluation** (Processing)
   - Compare score distributions across time periods
   - Flag anomalies (sudden score changes, outlier trips)
   - Generate summary statistics

4. **Registration** (Model step)
   - Package scoring weights and logic as a "model" artifact
   - Register in SageMaker Model Registry for version tracking
   - Enable A/B testing of different weight configurations

## Pipeline Pattern

This follows the pattern from [sagemaker-mlops-pipeline-starter](https://github.com/saranreddy/sagemaker-mlops-pipeline-starter):

- Define pipeline with SageMaker Pipelines SDK
- Use Parameters for S3 paths and dates
- Conditional registration based on evaluation results
- Manual approval gate before deploying to production scoring

## Execution

Planned execution:
- **Schedule:** Weekly (or on-demand)
- **Trigger:** EventBridge rule or manual execution
- **Outputs:** Scores for all trips in the past 7 days

## Implementation Notes

- Use `sagemaker.workflow.pipeline.Pipeline`
- Store pipeline definition in this directory
- Use Processing jobs with scikit-learn containers (no model training needed)
- Register scoring artifacts in Model Registry for versioning
