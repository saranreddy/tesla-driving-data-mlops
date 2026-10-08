resource "aws_glue_catalog_database" "teslamate" {
  name        = replace("${var.project_name}_data", "-", "_")
  description = "TeslaMate driving and charging data exported to Parquet"

  tags = {
    Name = "TeslaMate Data Catalog"
  }
}

resource "aws_glue_catalog_table" "drives" {
  database_name = aws_glue_catalog_database.teslamate.name
  name          = "drives"
  description   = "Tesla driving data exported from TeslaMate"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"              = "TRUE"
    "parquet.compression"   = "SNAPPY"
    "projection.enabled"    = "true"
    "projection.date.type"  = "date"
    "projection.date.range" = "2024-01-01,NOW"
    "projection.date.format" = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/raw/drives/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/raw/drives/"
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

resource "aws_glue_catalog_table" "charges" {
  database_name = aws_glue_catalog_database.teslamate.name
  name          = "charges"
  description   = "Tesla charging data exported from TeslaMate"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"              = "TRUE"
    "parquet.compression"   = "SNAPPY"
    "projection.enabled"    = "true"
    "projection.date.type"  = "date"
    "projection.date.range" = "2024-01-01,NOW"
    "projection.date.format" = "yyyy-MM-dd"
    "storage.location.template" = "s3://${aws_s3_bucket.data.id}/raw/charges/date=$${date}/"
  }

  partition_keys {
    name = "date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/raw/charges/"
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

resource "aws_athena_workgroup" "teslamate" {
  name        = "${var.project_name}-workgroup"
  description = "Athena workgroup for TeslaMate data queries"

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
