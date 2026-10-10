# Bronze Layer Database
resource "aws_glue_catalog_database" "bronze" {
  name        = replace("${var.project_name}_bronze", "-", "_")
  description = "Bronze layer: Raw TeslaMate data exported to Parquet"

  tags = {
    Name  = "TeslaMate Bronze Layer"
    Layer = "bronze"
  }
}

# Silver Layer Database
resource "aws_glue_catalog_database" "silver" {
  name        = replace("${var.project_name}_silver", "-", "_")
  description = "Silver layer: Quality-checked TeslaMate data"

  tags = {
    Name  = "TeslaMate Silver Layer"
    Layer = "silver"
  }
}

# Gold Layer Database (Insurance Use Case)
resource "aws_glue_catalog_database" "insurance" {
  name        = replace("${var.project_name}_insurance", "-", "_")
  description = "Gold layer: Insurance risk scoring and features"

  tags = {
    Name    = "TeslaMate Insurance Use Case"
    Layer   = "gold"
    UseCase = "insurance"
  }
}

# Legacy database for backward compatibility (maps to bronze)
resource "aws_glue_catalog_database" "teslamate" {
  name        = replace("${var.project_name}_data", "-", "_")
  description = "TeslaMate driving and charging data (legacy, points to bronze layer)"

  tags = {
    Name   = "TeslaMate Data Catalog (Legacy)"
    Notice = "Use teslamate_bronze for new queries"
  }
}

# ============================================================================
# BRONZE LAYER TABLES
# ============================================================================

resource "aws_glue_catalog_table" "bronze_drives" {
  database_name = aws_glue_catalog_database.bronze.name
  name          = "drives"
  description   = "Bronze: Raw driving data from TeslaMate"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/bronze/drives/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/bronze/drives/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "start_date"
      type = "timestamp"
    }
    columns {
      name = "end_date"
      type = "timestamp"
    }
    columns {
      name = "start_address"
      type = "string"
    }
    columns {
      name = "end_address"
      type = "string"
    }
    columns {
      name = "distance"
      type = "double"
    }
    columns {
      name = "duration_min"
      type = "double"
    }
    columns {
      name = "start_km"
      type = "double"
    }
    columns {
      name = "end_km"
      type = "double"
    }
    columns {
      name = "kwh_used"
      type = "double"
    }
    columns {
      name = "start_battery_level"
      type = "int"
    }
    columns {
      name = "end_battery_level"
      type = "int"
    }
    columns {
      name = "outside_temp_avg"
      type = "double"
    }
    columns {
      name = "speed_max"
      type = "double"
    }
    columns {
      name = "efficiency"
      type = "double"
    }
  }
}

resource "aws_glue_catalog_table" "bronze_charges" {
  database_name = aws_glue_catalog_database.bronze.name
  name          = "charges"
  description   = "Bronze: Raw charging data from TeslaMate"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/bronze/charges/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/bronze/charges/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "start_date"
      type = "timestamp"
    }
    columns {
      name = "end_date"
      type = "timestamp"
    }
    columns {
      name = "address"
      type = "string"
    }
    columns {
      name = "charge_energy_added"
      type = "double"
    }
    columns {
      name = "start_battery_level"
      type = "int"
    }
    columns {
      name = "end_battery_level"
      type = "int"
    }
    columns {
      name = "duration_min"
      type = "double"
    }
    columns {
      name = "cost"
      type = "double"
    }
  }
}

resource "aws_glue_catalog_table" "bronze_positions" {
  database_name = aws_glue_catalog_database.bronze.name
  name          = "positions"
  description   = "Bronze: One-second position readings from TeslaMate"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/bronze/positions/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/bronze/positions/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "drive_id"
      type = "bigint"
    }
    columns {
      name = "timestamp"
      type = "timestamp"
    }
    columns {
      name = "latitude"
      type = "double"
    }
    columns {
      name = "longitude"
      type = "double"
    }
    columns {
      name = "speed"
      type = "double"
    }
    columns {
      name = "power"
      type = "double"
    }
    columns {
      name = "odometer"
      type = "double"
    }
    columns {
      name = "ideal_battery_range_km"
      type = "double"
    }
    columns {
      name = "battery_level"
      type = "int"
    }
    columns {
      name = "outside_temp"
      type = "double"
    }
    columns {
      name = "elevation"
      type = "double"
    }
    columns {
      name = "fan_status"
      type = "int"
    }
    columns {
      name = "driver_temp_setting"
      type = "int"
    }
    columns {
      name = "passenger_temp_setting"
      type = "int"
    }
    columns {
      name = "is_climate_on"
      type = "boolean"
    }
    columns {
      name = "is_rear_defroster_on"
      type = "boolean"
    }
    columns {
      name = "is_front_defroster_on"
      type = "boolean"
    }
  }
}

# ============================================================================
# SILVER LAYER TABLES
# ============================================================================

resource "aws_glue_catalog_table" "silver_drives" {
  database_name = aws_glue_catalog_database.silver.name
  name          = "silver_drives"
  description   = "Silver: Quality-checked driving data with flags"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/silver/drives/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/silver/drives/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    # All bronze columns
    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "start_date"
      type = "timestamp"
    }
    columns {
      name = "end_date"
      type = "timestamp"
    }
    columns {
      name = "start_address"
      type = "string"
    }
    columns {
      name = "end_address"
      type = "string"
    }
    columns {
      name = "distance"
      type = "double"
    }
    columns {
      name = "duration_min"
      type = "double"
    }
    columns {
      name = "start_km"
      type = "double"
    }
    columns {
      name = "end_km"
      type = "double"
    }
    columns {
      name = "kwh_used"
      type = "double"
    }
    columns {
      name = "start_battery_level"
      type = "int"
    }
    columns {
      name = "end_battery_level"
      type = "int"
    }
    columns {
      name = "outside_temp_avg"
      type = "double"
    }
    columns {
      name = "speed_max"
      type = "double"
    }
    columns {
      name = "efficiency"
      type = "double"
    }

    # Quality columns
    columns {
      name = "quality_flag"
      type = "boolean"
    }
    columns {
      name = "pct_usable"
      type = "double"
    }
    columns {
      name = "failure_reasons"
      type = "string"
    }
  }
}

resource "aws_glue_catalog_table" "silver_positions" {
  database_name = aws_glue_catalog_database.silver.name
  name          = "silver_positions"
  description   = "Silver: Cleaned position readings with forward-filled sparse fields"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/silver/positions/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/silver/positions/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    # Same as bronze (cleaned, not augmented)
    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "drive_id"
      type = "bigint"
    }
    columns {
      name = "timestamp"
      type = "timestamp"
    }
    columns {
      name = "latitude"
      type = "double"
    }
    columns {
      name = "longitude"
      type = "double"
    }
    columns {
      name = "speed"
      type = "double"
    }
    columns {
      name = "power"
      type = "double"
    }
    columns {
      name = "odometer"
      type = "double"
    }
    columns {
      name = "ideal_battery_range_km"
      type = "double"
    }
    columns {
      name = "battery_level"
      type = "int"
    }
    columns {
      name = "outside_temp"
      type = "double"
    }
    columns {
      name = "elevation"
      type = "double"
    }
    columns {
      name = "fan_status"
      type = "int"
    }
    columns {
      name = "driver_temp_setting"
      type = "int"
    }
    columns {
      name = "passenger_temp_setting"
      type = "int"
    }
    columns {
      name = "is_climate_on"
      type = "boolean"
    }
    columns {
      name = "is_rear_defroster_on"
      type = "boolean"
    }
    columns {
      name = "is_front_defroster_on"
      type = "boolean"
    }
  }
}

resource "aws_glue_catalog_table" "silver_run_status" {
  database_name = aws_glue_catalog_database.silver.name
  name          = "silver_run_status"
  description   = "Silver: Per-run processing metadata"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/silver/_metadata/run_status/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/silver/_metadata/run_status/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "run_date"
      type = "timestamp"
    }
    columns {
      name = "process_date"
      type = "string"
    }
    columns {
      name = "success"
      type = "boolean"
    }
    columns {
      name = "message"
      type = "string"
    }
  }
}

# ============================================================================
# GOLD LAYER TABLES (Insurance Use Case)
# ============================================================================

resource "aws_glue_catalog_table" "ins_trip_features" {
  database_name = aws_glue_catalog_database.insurance.name
  name          = "ins_trip_features"
  description   = "Gold: Insurance driving behavior features"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/usecases/insurance/gold/ins_trip_features/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "date"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/usecases/insurance/gold/ins_trip_features/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "drive_id"
      type = "bigint"
    }
    columns {
      name = "date"
      type = "date"
    }
    columns {
      name = "hard_brakes_per_100mi"
      type = "double"
    }
    columns {
      name = "hard_accels_per_100mi"
      type = "double"
    }
    columns {
      name = "pct_time_over_80mph"
      type = "double"
    }
    columns {
      name = "night_minutes"
      type = "double"
    }
    columns {
      name = "pct_highway"
      type = "double"
    }
    columns {
      name = "miles"
      type = "double"
    }
    columns {
      name = "duration_hours"
      type = "double"
    }
    columns {
      name = "avg_temp_f"
      type = "double"
    }
    columns {
      name = "wh_per_km"
      type = "double"
    }
  }
}

resource "aws_glue_catalog_table" "ins_trip_scores" {
  database_name = aws_glue_catalog_database.insurance.name
  name          = "ins_trip_scores"
  description   = "Gold: Insurance risk scores (0-100, lower = safer)"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/usecases/insurance/gold/ins_trip_scores/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "date"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/usecases/insurance/gold/ins_trip_scores/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "drive_id"
      type = "bigint"
    }
    columns {
      name = "date"
      type = "date"
    }
    columns {
      name = "risk_score"
      type = "double"
    }
    columns {
      name = "score_category"
      type = "string"
    }
    columns {
      name = "top_risk_factors"
      type = "string"
    }
  }
}

# ============================================================================
# LEGACY TABLES (Backward Compatibility)
# ============================================================================

# Legacy drives table pointing to bronze
resource "aws_glue_catalog_table" "drives" {
  database_name = aws_glue_catalog_database.teslamate.name
  name          = "drives"
  description   = "Legacy table (use teslamate_bronze.drives instead)"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/bronze/drives/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/bronze/drives/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "start_date"
      type = "timestamp"
    }
    columns {
      name = "end_date"
      type = "timestamp"
    }
    columns {
      name = "start_address"
      type = "string"
    }
    columns {
      name = "end_address"
      type = "string"
    }
    columns {
      name = "distance"
      type = "double"
    }
    columns {
      name = "duration_min"
      type = "double"
    }
    columns {
      name = "start_km"
      type = "double"
    }
    columns {
      name = "end_km"
      type = "double"
    }
    columns {
      name = "kwh_used"
      type = "double"
    }
    columns {
      name = "start_battery_level"
      type = "int"
    }
    columns {
      name = "end_battery_level"
      type = "int"
    }
    columns {
      name = "outside_temp_avg"
      type = "double"
    }
    columns {
      name = "speed_max"
      type = "double"
    }
    columns {
      name = "efficiency"
      type = "double"
    }
  }
}

# Legacy charges table pointing to bronze
resource "aws_glue_catalog_table" "charges" {
  database_name = aws_glue_catalog_database.teslamate.name
  name          = "charges"
  description   = "Legacy table (use teslamate_bronze.charges instead)"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "parquet.compression"       = "SNAPPY"
    "projection.enabled"        = "true"
    "projection.date.type"      = "date"
    "projection.date.range"     = "2024-01-01,NOW"
    "projection.date.format"    = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/bronze/charges/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/bronze/charges/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "start_date"
      type = "timestamp"
    }
    columns {
      name = "end_date"
      type = "timestamp"
    }
    columns {
      name = "address"
      type = "string"
    }
    columns {
      name = "charge_energy_added"
      type = "double"
    }
    columns {
      name = "start_battery_level"
      type = "int"
    }
    columns {
      name = "end_battery_level"
      type = "int"
    }
    columns {
      name = "duration_min"
      type = "double"
    }
    columns {
      name = "cost"
      type = "double"
    }
  }
}

# ============================================================================
# ATHENA WORKGROUP
# ============================================================================

resource "aws_athena_workgroup" "teslamate" {
  name        = "${var.project_name}-workgroup"
  description = "Athena workgroup for TeslaMate data queries (all layers)"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = false

    result_configuration {
      output_location = "s3://${aws_s3_bucket.data.id}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = {
    Name = "TeslaMate Athena Workgroup"
  }
}
