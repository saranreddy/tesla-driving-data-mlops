resource "aws_security_group" "teslamate" {
  name        = "${var.project_name}-sg"
  description = "Security group for TeslaMate EC2 instance - no public inbound access"
  vpc_id      = aws_default_vpc.default.id

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "TeslaMate Security Group"
  }
}

resource "aws_default_vpc" "default" {
  tags = {
    Name = "Default VPC"
  }
}
