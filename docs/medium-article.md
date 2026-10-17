# From a DevOps Request to a Reviewed Pull Request: Building Agent-Assisted Automation

*Unpublished article draft. The local agent call is live; CI proposals use fixtures; Terraform tests use mocked providers. No real-cloud provisioning result is claimed.*

A request such as “create a private development bucket” looks small because the desired outcome fits in one sentence. The engineering work does not. Someone must resolve missing inputs, select an infrastructure pattern, explain the proposed resources, review the change, run checks, authorize execution, and establish what actually happened.

I built [Reviewed DevOps](https://github.com/Shrinidhikulkarni7/intelligent-automation) as a personal reference implementation of that chain. Its purpose is concrete: let a coding agent help author a change while keeping permission decisions in ordinary code and review controls.

The repository has three examples: a private encrypted object-storage bucket proposal, a diagnosis of an intentionally failed workflow, and a retention change from seven days to three. It uses native GitHub branches, pull requests, checks, summaries and artifacts. There is no separate service or database to operate.

The implementation and evidence distinguish three claims that are easy to blur together. A fixture can demonstrate deterministic orchestration. A live coding-agent call can demonstrate the adapter. A mocked Terraform test can demonstrate configuration behavior. None establishes that a resource was successfully provisioned in AWS.

## Why generating Terraform is only the beginning

A model can emit plausible configuration without knowing whether the request is authorized, whether its dependencies are reviewed, whether a bucket already belongs to another environment, or whether a lifecycle update will remove data sooner than intended.

Even valid Terraform is not sufficient. A provider is executable software. Planning can access credentials and external systems; it belongs inside an explicit trust boundary. Saved plans and state can contain sensitive data. Publishing them as convenient debugging artifacts would create another problem.

The lifecycle therefore has seven named stages:

```text
Request → Proposed change → Pull request → Validation
        → Authorized execution → Verification → Evidence
```

Each stage has a different proof obligation. A proposal must satisfy scope policy. A PR needs independent checks and review. Execution needs an explicit target and reviewed revision. Verification needs evidence from the system being changed. A fluent model response cannot replace any of those obligations.

The repository deliberately implements a small infrastructure language. The established pattern is a reviewed S3 bucket module. Requests outside that language stop for additional review rather than obtaining broader execution privileges.

## A small architecture with visible trust boundaries

The orchestration is Python with no third-party runtime dependencies. Its pieces are [request and proposal policy](https://github.com/Shrinidhikulkarni7/intelligent-automation/blob/main/devops_agent/core.py), an [agent adapter](https://github.com/Shrinidhikulkarni7/intelligent-automation/blob/main/devops_agent/adapter.py), isolated Git publication, evidence collection, and optional cloud execution.

A structured request specifies a version, operation, environment, resource, retention and descriptive text. The initial environment is `dev`, and retention must be an integer between one and thirty. Unsupported operations, additional fields and incomplete natural-language requests fail before inference.

The natural-language entry point has an intentionally narrow grammar. “Create a private bucket” does not contain a retention decision, so the parser does not silently invent one. More detailed descriptions can accompany the structured request. The structured target and retention remain authoritative when the prose conflicts with them.

The adapter receives only that request and the selected public configuration. It returns status, a serialized Terraform JSON document, assumptions, required inputs and diagnostics. The orchestrator records whether the result came from a fixture or a live call. Missing CLI authentication produces `integration not configured`; it never substitutes a canned response.

I verified the local Codex CLI integration with the owner's configured login. The adapter uses schema-constrained output, a temporary working directory, read-only sandbox, disabled approval requests and bounded subprocess I/O. Its default inference settings are one attempt, ninety seconds, low reasoning effort and a 48 KB output cap. Those are practical limits, not a verified monetary ceiling. Account-side limits remain necessary.

The local CLI also remains a trust consideration. Its authentication is real, and a read-only sandbox is not proof that every host-readable file is isolated. This reference uses public context only. A dedicated account or isolated runner is the next boundary for broader use.

## A complete request-to-proposal walkthrough

The creation example asks for a private development bucket with encryption, public access blocked and seven-day lifecycle expiration. A second structured request asks the agent to express labels through locals, add a descriptive tag and expose the bucket identifier.

This is the actual accepted live-generated configuration:

```json
{
  "locals": {
    "labels": {
      "Environment": "dev",
      "ManagedBy": "reviewed-devops",
      "Purpose": "development uploads"
    }
  },
  "module": {
    "app": {
      "bucket_name": "reviewed-devops-example-new-app",
      "retention_days": 7,
      "source": "../../modules/private_bucket",
      "tags": "${local.labels}"
    }
  },
  "output": {
    "bucket_id": {
      "value": "${module.app.bucket_id}"
    }
  }
}
```

The [checked-in result and provenance](https://github.com/Shrinidhikulkarni7/intelligent-automation/tree/main/examples/evidence/live-create) preserve that output. The proposal digest is `f47baeba33b18529504702a309be8c3aa2ea0b8e65c74c85ca9a1a9401700e64`. It is evidence of an observed adapter result, not a promise that another model call will produce identical bytes.

The agent authored the whole document, including locals, tags and an output. The policy permits that structure while recognizing only two exact references: `${local.labels}` and `${module.app.bucket_id}`. Tags must be bounded literal public text. Other expressions, providers, data sources, resources, module sources and file paths are rejected.

That balance matters. Replacing generation with string substitution would demonstrate a different capability. Accepting arbitrary generated Terraform would create a much larger execution problem. Here, the model can compose within a reviewed pattern, and expanding the pattern requires a reviewed code change.

The module defines the bucket, server-side AES256 encryption, all four public-access blocks, bucket-owner enforcement and lifecycle expiration. The bucket also has `force_destroy = false` and `prevent_destroy`. These are configuration controls, not proof that every real access path is safe or that object expiration is reversible.

The bundle contains the generated file, a sanitized report and a concise PR description. Publication clones the trusted source into a temporary directory, changes only the permitted configuration path and commits a stable proposal branch. Without `--remote`, it produces a portable Git branch bundle. With explicitly requested remote publication, it pushes and creates or updates the PR.

The live-generated proposal is [PR #1](https://github.com/Shrinidhikulkarni7/intelligent-automation/pull/1); its diff contains only the new configuration file.

The create example targets `dev/new-app`. The retention example uses a separate checked-in `dev/app` baseline. This avoids calling an unchanged existing configuration a successful resource-creation proposal. Neither configuration implies that a corresponding cloud resource already exists.

## Making repeated requests understandable

Proposal identity is based on target and operation, not the exact wording of the prompt. Rephrasing the same desired change uses the same branch and open PR. An identical remote configuration returns the existing PR; an updated desired configuration uses a Git lease to detect competing publishers.

A moved base requires regeneration. Existing proposal branches with unrelated edits require manual reconciliation. This is a small repository-based coordination mechanism, not a durable work queue.

Local operations use advisory environment locks. Hosted proposal and cloud jobs share a GitHub concurrency group with cancellation disabled. Remote Terraform backend locking protects independent clients using the same state. These controls have distinct scopes: a local lock does not coordinate machines, and GitHub concurrency can supersede pending work. The actual run history still matters.

For retention changes, the allowed diff is even narrower. The policy copies both documents, normalizes the one allowed field and compares everything else:

```python
before, after = json.loads(canonical(current)), json.loads(canonical(value))
before["module"]["app"]["retention_days"] = after["module"]["app"]["retention_days"]
if before != after:
    raise Rejected("retention update changed unrelated configuration")
```

A proposal that also changes tags, identity or module source fails. The report shows seven days before and three afterward. A reviewer must still consider the data consequence: shorter expiration can remove existing objects sooner even when the infrastructure action is an update.

## What validation actually establishes

The [credential-free check command](https://github.com/Shrinidhikulkarni7/intelligent-automation/blob/main/scripts/check.py) runs Python tests, formats Terraform, validates generated roots and executes mocked-provider tests. The verified local run passed thirty-six Python tests and six Terraform test runs: three module scenarios and one generated-root run for each fixture plus the recorded live proposal.

The module tests assert public-access blocks, encryption, owner enforcement, expiration at seven and three days, and rejection of zero-day retention. The Python tests cover invalid scope, incomplete text, extra fields, unsafe generated blocks, unrelated updates, duplicates, subprocess limits, adapter failures, evidence handling and explicit authorization gates.

Mocking is important to the reproduction path. Terraform still loads a real pinned provider plugin, but the test's AWS operations are mocked. No cloud account is needed. This checks configuration behavior; it does not verify IAM permissions, service availability, globally unique bucket names or actual object deletion behavior. [HashiCorp's provider-mocking documentation](https://developer.hashicorp.com/terraform/language/tests/mocking) describes that testing facility.

One test exposed a publication bug: the first implementation checked `git diff` before staging a new file, so a creation proposal appeared unchanged. I fixed publication to stage the allowed path and inspect the staged diff. That is the sort of integration error a successful model response would never reveal by itself.

Hosted validation then exposed a second portability issue: the generated-root tests reused an unpacked provider, while the committed lockfile had only the macOS content hash. I added registry-verified Linux x64 checksums with `terraform providers lock -platform=darwin_arm64 -platform=linux_amd64`. The fix preserves checksum enforcement; it does not bypass the failing check.

The first local Terraform attempt also failed because the surrounding process sandbox prevented the provider plugin from starting. Running the same mocked tests with appropriate local process access passed. That was a test-environment constraint, not an observed AWS failure.

## GitHub Actions and authorized execution

The [workflows](https://github.com/Shrinidhikulkarni7/intelligent-automation/tree/main/.github/workflows) use thin entry points and reusable workflows. Substantial logic remains in Python so it can run locally. PR validation has read-only repository permissions, no cloud identity and no agent credential. Checkout credentials are not persisted.

The credential-bearing proposal path is manually dispatched, restricted to main and gated by an explicit repository opt-in plus a protected environment. It is shipped disabled. Its owner supplies an agent API key only after reviewing those settings. The verified local login does not establish that this hosted credential mode works.

Automation-created PR checks need explicit attention. The [current GitHub trigger documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow) describes approval-required runs for certain PR events created with `GITHUB_TOKEN`; ordinary pushes with that token do not start downstream workflows. A GitHub App token or PAT follows a different event path. A created PR is therefore not evidence of completed validation. Inspect the actual checks and deployment behavior.

The optional cloud workflow is separately gated and has not provisioned AWS resources. It requires protected plan and apply environments, owner-configured OIDC roles, a pre-existing private encrypted S3 backend with locking, and a full reviewed revision merged into main. The authorization string names the action, target and revision. The CLI cannot prove a human reviewed a commit; repository protections and environment approval enforce that part.

Planning produces a sanitized action summary and a digest. A separate apply dispatch supplies that reviewed digest. Apply replans, rejects deletions, replacements and unapproved resource types, checks the digest and applies the exact locally saved plan. It then runs a provider-backed follow-up plan and reports success only if no changes remain.

Raw saved plans and state are never uploaded. [Terraform's plan documentation](https://developer.hashicorp.com/terraform/cli/commands/plan) explains why a saved plan requires sensitive-data handling. A failed apply or uncertain verification reports incomplete work. Nothing automatically destroys resources, force-unlocks state or claims rollback succeeded. Digest stability and the full real-cloud behavior still require an explicitly authorized live exercise.

## Diagnosing a failure without manufacturing certainty

The second example deliberately omits `DEMO_REGION` from a workflow step. Its local reproduction exits with code two and emits:

```text
CONFIG_ERROR: DEMO_REGION must equal us-east-1
```

The diagnosis cites `sanitized-log:L1`. That line establishes that the checker observed an absent or unequal value. It cannot distinguish those causes by itself. The inspected local workflow corroborates omission, permitting a proposed step-level environment change. A separate test verifies that `DEMO_REGION=us-east-1` makes the step pass.

The [hosted intentional-failure run](https://github.com/Shrinidhikulkarni7/intelligent-automation/actions/runs/39005846380) also emitted this error. Its stored diagnosis cites `sanitized-log:L5`, preserves the selected commit, and leaves the patch unset because the log collector has not fetched that revision’s workflow configuration.

The workflow remains intentionally broken so the example can be reproduced. The report does not automatically apply its fix.

A selected hosted-run collector records the run revision and failed job, bounds metadata and log output, and redacts common credential forms, URLs and user paths. Ambiguous or oversized evidence stops collection. Redaction is defense in depth; arbitrary logs still need inspection before publication.

Hosted log evidence alone does not justify a patch in this initial implementation. The report separates confirmed observations, suspected causes, missing evidence and a next check. Unknown errors produce no invented root cause. The sample analyzer is deterministic; I do not describe it as a live AI diagnosis merely because the repository has an agent adapter elsewhere.

## Reproducing and extending the reference

Start with a clone, Python 3.11+, Git and Terraform. Run `python3 scripts/check.py`, initialize the pinned public provider, then run `python3 scripts/check.py --terraform`. The [three walkthroughs](https://github.com/Shrinidhikulkarni7/intelligent-automation/blob/main/docs/examples.md) give complete commands for proposal bundles, diagnosis and retention updates. A configured Codex login is needed only when selecting the live adapter. GitHub publication is an explicit additional command.

The remaining limitations are concrete. Natural-language parsing is narrow. Only one infrastructure pattern and local agent integration are verified. Host isolation is limited. Hosted agent credentials and real-cloud execution are optional, unverified paths. No mock establishes AWS correctness, and no inference limit here establishes a hard billing cap.

Useful next work is to test the optional credential modes in an isolated owner-controlled environment, strengthen host isolation, and extend policies only when a real use case requires them. Drift remediation, dependency updates, resizing and decommissioning can use the same review lifecycle, but each needs its own diff policy, authorization and verification. Destructive decommissioning needs a separate design.

The working result is a bounded path from request to reviewable evidence. Its value depends on keeping those boundaries explicit as the examples grow.
