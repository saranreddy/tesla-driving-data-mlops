resource "random_password" "teslamate_encryption_key" {
  length  = 64
  special = false
}

resource "random_password" "postgres_password" {
  length  = 32
  special = true
}

resource "random_password" "grafana_admin_password" {
  length  = 24
  special = true
}

resource "aws_ssm_parameter" "teslamate_encryption_key" {
  name  = "/${var.project_name}/teslamate/encryption-key"
  type  = "SecureString"
  value = random_password.teslamate_encryption_key.result

  tags = {
    Name = "TeslaMate Encryption Key"
  }
}

resource "aws_ssm_parameter" "postgres_password" {
  name  = "/${var.project_name}/postgres/password"
  type  = "SecureString"
  value = random_password.postgres_password.result

  tags = {
    Name = "PostgreSQL Password"
  }
}

resource "aws_ssm_parameter" "grafana_admin_password" {
  name  = "/${var.project_name}/grafana/admin-password"
  type  = "SecureString"
  value = random_password.grafana_admin_password.result

  tags = {
    Name = "Grafana Admin Password"
  }
}
