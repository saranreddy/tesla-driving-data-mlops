variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "instance_type" {
  description = "EC2 instance type for TeslaMate host (t3.micro is free-tier eligible for all accounts; t4g.micro is 25% cheaper after free tier)"
  type        = string
  default     = "t3.micro"
}

variable "volume_size" {
  description = "Root EBS volume size in GB (30 GB covered by free tier)"
  type        = number
  default     = 30
}

variable "project_name" {
  description = "Project name prefix for resource naming"
  type        = string
  default     = "teslamate-mlops"
}

variable "backup_retention_days" {
  description = "Number of days to retain database backups in S3"
  type        = number
  default     = 30
}

variable "data_lifecycle_days" {
  description = "Number of days before moving S3 data to Infrequent Access storage"
  type        = number
  default     = 90
}
