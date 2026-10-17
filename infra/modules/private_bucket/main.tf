terraform {
  required_version = ">= 1.7.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.100.0"
    }
  }
}

variable "bucket_name" {
  type = string
}

variable "retention_days" {
  type = number
  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 30 && floor(var.retention_days) == var.retention_days
    error_message = "Retention must be an integer between 1 and 30 days."
  }
}

variable "tags" {
  type = map(string)
}

resource "aws_s3_bucket" "app" {
  bucket        = var.bucket_name
  force_destroy = false
  tags          = var.tags
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "app" {
  bucket                  = aws_s3_bucket.app.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app" {
  bucket = aws_s3_bucket.app.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "app" {
  bucket = aws_s3_bucket.app.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "app" {
  bucket = aws_s3_bucket.app.id
  rule {
    id     = "expire-development-objects"
    status = "Enabled"
    filter {}
    expiration {
      days = var.retention_days
    }
  }
}

output "bucket_id" {
  value = aws_s3_bucket.app.id
}
