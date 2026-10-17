# Reproduce the examples

Run commands from the repository root. Python fixture examples need no agent or cloud credential. Follow [setup](setup.md) for provider installation and optional GitHub authentication.

## Create

```sh
python3 -m devops_agent.cli propose \
  --text 'Create a private object-storage bucket for a development application, with encryption, public access blocked, and a 7-day lifecycle policy.' \
  --adapter fixture --fixture examples/fixtures/create.json
cat .out/dev-app-create/main.tf.json
cat .out/dev-app-create/pr.md
python3 -m devops_agent.cli publish .out/dev-app-create \
  --repo YOUR-OWNER/YOUR-REPOSITORY
```

This emits `.out/dev-app-create/branch.bundle` containing a committed proposal branch. It does not push. On an already committed clone, inspect it with:

```sh
git fetch .out/dev-app-create/branch.bundle proposal/dev-app-create
git diff HEAD FETCH_HEAD -- infra/environments/dev-new/main.tf.json
```

For a real PR, authenticate `gh` against your **public** fork, ensure its main matches the source checkout, and configure Git HTTPS authentication (`gh auth setup-git --hostname github.com`). Then add `--remote` to `publish`. This pushes a stable proposal branch and creates/updates its PR. It needs contents write and pull-request write access. The human's GitHub token is used only for publication, never for inference.

For live generation, replace the fixture flags with `--adapter codex`, or use `examples/requests/generated-layout.json` to ask for labels through locals and an output. The checked-in [live example](../examples/evidence/live-create/main.tf.json) was authored through that integration and passed policy plus mocked validation. CI still uses the explicit fixture.

Unsupported text such as `Create production networking` or incomplete bucket requests without retention are rejected. A structured request with `environment: prod`, unsafe retention, extra fields, a new provider or a model's `approved: true` cannot authorize a proposal. Structured inputs take priority over ambiguous descriptive text. Resolve requested scope changes explicitly rather than guessing.

## Diagnose

```sh
python3 -m devops_agent.cli collect --out .out/failure.json
python3 -m devops_agent.cli diagnose .out/failure.json --out .out/diagnosis.json
```

This executes the same deliberately broken step as `intentional-failure.yml` locally. Its stderr is:

```text
CONFIG_ERROR: DEMO_REGION must equal us-east-1
```

The report cites `sanitized-log:L1`. The error confirms an absent or unequal value; it does not distinguish those causes. Inspecting the local workflow corroborates omission, permitting the proposed one-step environment fix. The workflow stays intentionally broken so the example remains reproducible. The test suite checks that setting `DEMO_REGION=us-east-1` makes that step pass.

To inspect a selected hosted run from a public repository:

```sh
python3 -m devops_agent.cli collect --repo YOUR-OWNER/YOUR-REPOSITORY \
  --run SELECTED-RUN-ID --out .out/hosted-failure.json
python3 -m devops_agent.cli diagnose .out/hosted-failure.json
```

The collector records the selected revision and failed job, caps metadata/log sizes and redacts common credential forms, URLs and user paths. Too-large/ambiguous/missing evidence stops collection. Do not publish arbitrary logs without manual inspection: regex redaction is not proof that every secret is removed. Hosted log evidence alone produces no automatic patch. Unknown errors produce missing evidence and a next check, with no fabricated root cause.

The sample diagnosis is deterministic, not a live AI diagnosis. That is a deliberate boundary: a future agent may summarize these facts but cannot create stronger evidence by inference.

## Retention

```sh
python3 -m devops_agent.cli propose \
  --request examples/requests/retention.json \
  --adapter fixture --fixture examples/fixtures/retention.json
python3 -m devops_agent.cli publish .out/dev-app-retention \
  --repo YOUR-OWNER/YOUR-REPOSITORY
```

The baseline at `infra/environments/dev/main.tf.json` has seven-day expiration. The proposal changes only that value to three. The policy compares the entire parsed configuration after normalizing the one allowed field; unrelated tag, identity, module or output changes fail. This is an existing **managed configuration** example, not evidence of a deployed resource.

Repeating the same request uses the same bundle and branch. Hosted publication returns the open PR if its desired configuration matches; a changed desired retention updates that proposal with a Git lease. Concurrent publication or moved main is rejected for retry/regeneration. Separate creation and retention requests have separate branches, but all operations for dev share a lock/concurrency group.

A three-day lifecycle may expire existing objects earlier. Review that consequence even though Terraform labels the change an update. No real execution is performed by these commands.
