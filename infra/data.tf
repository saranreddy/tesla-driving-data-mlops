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
