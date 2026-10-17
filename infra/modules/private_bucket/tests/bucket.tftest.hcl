mock_provider "aws" {}

variables {
  bucket_name    = "reviewed-devops-test"
  retention_days = 7
  tags = {
    Environment = "dev"
    ManagedBy   = "reviewed-devops"
  }
}

run "private_encrypted_bucket" {
  command = plan
  assert {
    condition     = aws_s3_bucket_public_access_block.app.block_public_acls && aws_s3_bucket_public_access_block.app.block_public_policy && aws_s3_bucket_public_access_block.app.ignore_public_acls && aws_s3_bucket_public_access_block.app.restrict_public_buckets
    error_message = "All public access blocks are required."
  }
  assert {
    condition     = one(aws_s3_bucket_server_side_encryption_configuration.app.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"
    error_message = "Encryption is required."
  }
  assert {
    condition     = one(aws_s3_bucket_lifecycle_configuration.app.rule).expiration[0].days == 7
    error_message = "Seven-day retention expected."
  }
  assert {
    condition     = one(aws_s3_bucket_ownership_controls.app.rule).object_ownership == "BucketOwnerEnforced" && !aws_s3_bucket.app.force_destroy
    error_message = "Owner enforcement and non-force deletion required."
  }
}

run "three_day_change" {
  command = plan
  variables {
    retention_days = 3
  }
  assert {
    condition     = one(aws_s3_bucket_lifecycle_configuration.app.rule).expiration[0].days == 3
    error_message = "Retention update did not take effect."
  }
}

run "reject_zero_retention" {
  command = plan
  variables {
    retention_days = 0
  }
  expect_failures = [var.retention_days]
}
