output "instance_id" {
  description = "EC2 instance ID for TeslaMate host"
  value       = aws_instance.teslamate.id
}

output "s3_bucket_name" {
  description = "S3 bucket name for TeslaMate data and backups"
  value       = aws_s3_bucket.data.id
}

output "glue_database_name" {
  description = "Glue Data Catalog database name"
  value       = aws_glue_catalog_database.teslamate.name
}

output "athena_workgroup" {
  description = "Athena workgroup for querying TeslaMate data"
  value       = aws_athena_workgroup.teslamate.name
}

output "ssm_parameters" {
  description = "SSM Parameter Store paths for secrets"
  value = {
    encryption_key   = aws_ssm_parameter.teslamate_encryption_key.name
    postgres_password = aws_ssm_parameter.postgres_password.name
    grafana_password  = aws_ssm_parameter.grafana_admin_password.name
  }
}

output "connect_command" {
  description = "AWS CLI commands to connect to TeslaMate and Grafana"
  value = <<-EOT
    # Connect to TeslaMate UI (port 4000):
    aws ssm start-session --target ${aws_instance.teslamate.id} --document-name AWS-StartPortForwardingSession --parameters "portNumber=4000,localPortNumber=4000" --region ${var.aws_region}
    # Then open: http://localhost:4000

    # Connect to Grafana UI (port 3000):
    aws ssm start-session --target ${aws_instance.teslamate.id} --document-name AWS-StartPortForwardingSession --parameters "portNumber=3000,localPortNumber=3000" --region ${var.aws_region}
    # Then open: http://localhost:3000
    # Username: admin
    # Get password: aws ssm get-parameter --name ${aws_ssm_parameter.grafana_admin_password.name} --with-decryption --query 'Parameter.Value' --output text --region ${var.aws_region}
  EOT
}
