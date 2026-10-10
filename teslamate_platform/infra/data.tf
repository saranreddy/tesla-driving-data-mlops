data "aws_caller_identity" "current" {}

locals {
  # Determine architecture based on instance type family
  # t4g/c7g/m7g = arm64 (Graviton), t2/t3/m5/c5 = x86_64
  is_graviton   = length(regexall("^(t4g|c7g|m7g|c6g|m6g|r6g|a1)\\.", var.instance_type)) > 0
  architecture  = local.is_graviton ? "arm64" : "x86_64"
  ami_arch_name = local.is_graviton ? "arm64" : "amd64"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-${local.ami_arch_name}-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = [local.architecture]
  }
}

# Look up (do not manage) the account's default VPC. Using a data source instead of
# aws_default_vpc avoids Terraform adopting and re-tagging a pre-existing, shared VPC.
data "aws_vpc" "default" {
  default = true
}

# AZs that actually offer the chosen instance type (e.g. t4g.* is not offered in us-east-1e)
data "aws_ec2_instance_type_offerings" "supported" {
  location_type = "availability-zone"
  filter {
    name   = "instance-type"
    values = [var.instance_type]
  }
}

# Default subnets in the default VPC, restricted to AZs that support the instance type
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
  filter {
    name   = "availability-zone"
    values = data.aws_ec2_instance_type_offerings.supported.locations
  }
}
