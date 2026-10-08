resource "aws_instance" "teslamate" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.teslamate.name
  vpc_security_group_ids = [aws_security_group.teslamate.id]
  subnet_id              = sort(data.aws_subnets.default.ids)[0]

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.volume_size
    encrypted             = true
    delete_on_termination = true

    tags = {
      Name = "TeslaMate Root Volume"
    }
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    aws_region     = var.aws_region
    project_name   = var.project_name
    s3_bucket      = aws_s3_bucket.data.id
    encryption_key = aws_ssm_parameter.teslamate_encryption_key.name
    postgres_pass  = aws_ssm_parameter.postgres_password.name
    grafana_pass   = aws_ssm_parameter.grafana_admin_password.name
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  tags = {
    Name = "TeslaMate Host"
  }

  depends_on = [
    aws_ssm_parameter.teslamate_encryption_key,
    aws_ssm_parameter.postgres_password,
    aws_ssm_parameter.grafana_admin_password
  ]

  # Protect the live instance from replacement. The most_recent AMI changes frequently,
  # and user_data edits would normally stop/start the instance. Since Postgres data lives
  # on the root volume, replacement or restart without backup would cause data loss.
  # To deliberately rebuild: back up first, then: terraform apply -replace=aws_instance.teslamate
  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

resource "aws_dlm_lifecycle_policy" "teslamate_daily" {
  description        = "Daily snapshots of TeslaMate EBS volume"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]

    schedule {
      name = "Daily snapshots"

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["03:00"]
      }

      retain_rule {
        count = 7
      }

      tags_to_add = {
        SnapshotCreator = "DLM"
      }

      copy_tags = true
    }

    target_tags = {
      Name = "TeslaMate Root Volume"
    }
  }

  tags = {
    Name = "TeslaMate Daily Snapshots"
  }
}

resource "aws_iam_role" "dlm" {
  name = "${var.project_name}-dlm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "dlm.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "DLM Service Role"
  }
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}
