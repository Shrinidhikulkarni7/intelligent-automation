# Public implementation sources

Consulted while building this repository on 2026-10-17. Product and hosted behavior can change; check your deployed versions.

- [GitHub workflow triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow): GITHUB_TOKEN event behavior, approval-required PR checks, manual dispatch.
- [GitHub secure use reference](https://docs.github.com/en/actions/reference/security/secure-use): untrusted inputs and immutable action pinning.
- [Terraform provider mocking](https://developer.hashicorp.com/terraform/language/tests/mocking): mocked tests, Terraform 1.7+.
- [Terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan): provider execution and sensitive saved plans.
- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3): remote state encryption, versioning and lockfiles.
- [OpenAI Codex structured repair-loop example](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex): noninteractive `codex exec` and schema-constrained output. Local `codex exec --help` was checked for the installed 0.163.0 flags.

The project code and examples are original. These sources inform interface and security choices; they do not establish that the optional real-cloud path has been exercised.
