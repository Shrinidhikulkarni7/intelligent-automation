# Setup

## Credential-free demonstration

Clone your public repository or this repository. Use Python 3.11+, Git and Terraform; the verified version is 1.16.4. Python code runs directly; package installation is optional (`python3 -m pip install -e .`). No third-party Python runtime package is required.

```sh
git clone https://github.com/Shrinidhikulkarni7/intelligent-automation.git
cd intelligent-automation
python3 scripts/check.py
terraform -chdir=infra/modules/private_bucket init -backend=false -input=false -lockfile=readonly
python3 scripts/check.py --terraform
```

Terraform downloads the pinned AWS provider from the public registry. Lockfiles include registry-signed package hashes and content hashes for macOS ARM and Linux x64. Generated-root tests reuse this locally installed provider. First use needs internet and adequate disk space. Mocked provider plugins still need permission to start processes/local sockets; some OS sandboxes deny this. Run the tests in a trusted local environment or the unprivileged GitHub runner, without cloud credentials.

The suite checks requests, generated-code scope, duplicates, subprocess limits, adapter failures, evidence boundaries, local branch creation, revision-bound authorization and mocked Terraform behavior. It does not test AWS provisioning or the optional credential-bearing Actions integration.

## Optional local agent and GitHub PRs

Install Codex CLI 0.163.0 using the upstream installation instructions and authenticate your own account. `codex login status` must succeed. Use `--adapter codex` explicitly. Missing credentials never select a fixture. Inference may consume your account's allowance; set provider-side limits and the CLI timeout/attempt/output settings described in [adapters](adapters.md).

For public GitHub publication, authenticate `gh` only to github.com, configure Git HTTPS auth and use your public repository's owner/name. Remote main must match the trusted source checkout. `publish` without `--remote` is local. Remote publication requires contents write and pull-request write. It never merges the PR.

## Optional Actions agent integration — disabled

Do not enable until you have reviewed the workflows and established environment protections. The shipped manual entry point requires `ENABLE_AGENT_PROPOSALS=true` and a protected `agent-proposals` environment. Store an owner-supplied API key as `AGENT_API_KEY` there and require reviewer approval. Enable the repository setting that permits Actions to create PRs only after review. We have not enabled these settings or tested owner-key authentication in a hosted proposal run.

The job uses `GITHUB_TOKEN` with contents/write and pull-requests/write only during publication; inference receives no GitHub credential. Checks need separate attention. The [current GitHub trigger documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow) says automation-created `opened`, `synchronize` and `reopened` PR events can create **approval-required** workflow runs with `GITHUB_TOKEN`; ordinary push events do not create downstream runs. A suitably scoped GitHub App token or PAT can trigger PR checks without that approval path. Verify your actual GitHub deployment behavior, PR check state and repository policy. Do not infer validation from successful PR creation. Local user-token publication is a different path and its observed checks are recorded in verification.

## Optional real cloud integration — disabled and untested against AWS

No default command provisions infrastructure. This path requires owner configuration and explicit authorization. Do not enable it merely to run the examples.

Before enabling, review Terraform/module/provider code and the execution implementation. Create a private S3 state bucket separately with encryption, versioning, restricted access and retention/recovery policy. Configure native S3 lockfile permissions. Backend bootstrap is deliberately excluded. Never commit state, credentials, actual backend identifiers or saved plans.

Create protected `cloud-plan` and `cloud-apply` GitHub environments with required reviewers and default-branch deployment restrictions. Configure separate OIDC roles where practical. Restrict AWS trust by repository and environment subject; scope IAM to the intended buckets and state key/lockfile. Set environment variables `AWS_ROLE_ARN`, `AWS_ACCOUNT_ID`, and `STATE_BUCKET`. Only then, with explicit owner authorization, set repository `ENABLE_CLOUD_EXECUTION=true`. None of these resources or settings was created by this task.

The example bucket names are placeholders. Adapt the code's allowed identity and Terraform configuration in a reviewed PR before using a globally unique real bucket name. The existing-resource example needs correctly managed/imported state; local checked-in configuration alone is not proof that AWS has that resource. Do not use creation to adopt an existing bucket implicitly.

A plan dispatch requires a full merged revision, target `dev/app` or `dev/new-app`, and the exact string `plan:TARGET:REVISION`. The workflow rejects other refs/scopes before obtaining cloud identity. Planning can execute providers and contact AWS. Review the sanitized resource/action summary, configuration and plan digest; inspect sensitive plan details only in an approved private environment when necessary.

An apply dispatch is separate and requires `apply:TARGET:REVISION` plus the prior reviewed plan digest. It replans under remote locking, rejects deletion/replacement or unapproved resources, checks that digest, applies the exact local saved plan and runs a provider-backed follow-up plan. Any intervening change invalidates the digest. Digest stability across separate AWS runs is not verified; unexpected differences intentionally stop execution. A successful apply is reported only after no-change verification.

The local `execute` command has equivalent explicit gates; it additionally requires `REVIEWED_DEVOPS_LIVE=enabled` and an encrypted, locked backend file. Fetch `origin/main` freshly first. The CLI cannot independently prove human review; branch protection, environment approvals and correct IAM are owner responsibilities. This is a reference enforcement layer, not an unbypassable administrative control.

No code force-unlocks state, destroys after failure or automatically approves destructive changes. Failures may leave partial resources; investigate before retrying. State and saved plans remain temporary and are never uploaded. Configure runner and account security appropriate to your environment before any live use.
