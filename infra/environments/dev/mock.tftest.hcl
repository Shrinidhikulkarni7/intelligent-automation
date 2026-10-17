mock_provider "aws" {}

run "generated_configuration" {
  command = plan
}
