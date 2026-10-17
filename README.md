# Intelligent Automation

A personal, public reference project for turning a plain-language DevOps request into a bounded proposal, a pull request, validation, and explicitly authorized execution.

```text
Request → Proposed change → Pull request → Validation
        → Authorized execution → Verification → Evidence
```

The agent authors configuration and explains its assumptions. Python controls scope, inputs, publication, locking and execution. An AI response cannot approve infrastructure access.

## Watch the idea

[▶ Watch: One request, from setup to cleanup](https://youtu.be/d58-kT3VGu0)

A short film illustrating a conversational DevOps workflow—from requesting an environment through approval, deployment, verification and cleanup.

Read the full article: [Building a Conversational Control Plane for DevOps](https://shrinidhikulkarni.vercel.app/writing/building-a-conversational-control-plane-for-devops).

*The film illustrates the broader vision. This repository implements smaller, bounded examples rather than the complete system shown.*

## Start without credentials

Requires macOS/Linux (or WSL), Python 3.11+, Git, and Terraform 1.7–1.x (verified with 1.16.4). There are no Python runtime dependencies. Run from the repository root:

```sh
python3 scripts/check.py
terraform -chdir=infra/modules/private_bucket init -backend=false -input=false -lockfile=readonly
python3 scripts/check.py --terraform
```

The second command downloads the pinned public AWS provider. The tests use **mocked providers**, without cloud credentials or billable resources. They check configuration behavior, not provisioning, IAM, reachability or AWS guarantees.

## Three examples

| Example | Reproduce | Evidence |
|---|---|---|
| Private encrypted bucket → Terraform proposal / PR | [Create walkthrough](docs/examples.md#create) | [Live agent proposal](examples/evidence/live-create/report.json) |
| Failed pipeline → evidence-linked diagnosis | [Diagnosis walkthrough](docs/examples.md#diagnose) | [Sanitized local diagnosis](examples/evidence/local-diagnosis.json) |
| Existing seven-day setting → three-day proposal / PR | [Retention walkthrough](docs/examples.md#retention) | [Fixture proposal](examples/evidence/retention/report.json) |

CI uses explicitly selected **deterministic fixtures**. A real local Codex CLI integration was also exercised; its sanitized result is checked in. Other agents remain extension points. Hosted run and PR evidence is recorded in [verification](docs/verification.md).

## Boundaries

The supported infrastructure pattern is one reviewed private S3 bucket module. Generated module calls, literal tags, optional label locals and an approved output are allowed; arbitrary providers, resources, functions, dependencies and file changes are rejected. New patterns require code and infrastructure review. Natural-language parsing intentionally accepts a small grammar; structured requests carry explicit target and retention inputs.

Credential-bearing proposal and cloud workflows require manual dispatch, opt-in repository variables, and protected environments. They are **not enabled by this project**. The optional cloud path uses merged reviewed revisions, short-lived AWS identity, encrypted remote state, locking, a reviewed plan digest and post-apply verification. It has not been exercised against real infrastructure. No plan or state is uploaded.

This is a working reference with narrow examples, not a universal production platform. It has no chatbot service, database, queue or dashboard.

- [Setup: demonstrations vs live integrations](docs/setup.md)
- [Architecture and trust boundaries](docs/architecture.md)
- [Agent adapter contract](docs/adapters.md)
- [Published article](https://shrinidhikulkarni.vercel.app/writing/building-a-conversational-control-plane-for-devops)
- [Sources](docs/sources.md)
