resource "aws_iam_role" "teslamate_instance" {
  name = "${var.project_name}-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "TeslaMate Instance Role"
  }
}

resource "aws_iam_role_policy" "teslamate_s3" {
  name = "${var.project_name}-s3-access"
  role = aws_iam_role.teslamate_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "teslamate_ssm" {
  name = "${var.project_name}-ssm-access"
  role = aws_iam_role.teslamate_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "teslamate_ssm_managed" {
  role       = aws_iam_role.teslamate_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "teslamate" {
  name = "${var.project_name}-instance-profile"
  role = aws_iam_role.teslamate_instance.name

  tags = {
    Name = "TeslaMate Instance Profile"
  }
}
