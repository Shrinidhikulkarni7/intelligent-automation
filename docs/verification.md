# Verification record

Observed on 2026-10-17. Repository code and stored sanitized evidence are authoritative; this record does not claim a real-cloud deployment.

| Check | Observed result |
|---|---|
| Python policy/orchestration suite | 36 tests passed locally |
| Terraform module tests | 3 passed with mocked AWS provider |
| Generated roots: create fixture, retention fixture, recorded live output | 1 mocked test each passed; fmt and validate passed |
| actionlint 1.7.11 | All workflows passed |
| Live Codex CLI 0.163.0, local owner login | Two public calls passed policy; second generated locals, Purpose label and output |
| Intentionally failing local step | Exit 2 with the documented configuration error |
| Proposed configuration fix | Correct environment makes the step exit 0 in a test |
| Local branch publication | Both proposal branches verified in isolated test repositories; caller checkout unchanged |
| Unsafe requests/proposals, missing agent auth, failures, limits, duplicate identity, locks | Covered by passing Python tests |
| Real AWS plan/apply | Not run; optional and disabled |
| Hosted owner-key agent workflow | Not enabled or run |
| Medium publication | Not published; draft only |

Stored live result: [configuration](../examples/evidence/live-create/main.tf.json), [report](../examples/evidence/live-create/report.json), [PR description](../examples/evidence/live-create/pr.md). The recorded output is regression-tested as data in CI; CI does not make a live model call.

Hosted PR and workflow results are added here only after observing the actual runs. No success is inferred from workflow syntax or local tests.

## Hosted evidence observed

- [Live-generated create PR #1](https://github.com/Shrinidhikulkarni7/intelligent-automation/pull/1): only `infra/environments/dev-new/main.tf.json` is proposed.
- [Intentional failure run 39005846380](https://github.com/Shrinidhikulkarni7/intelligent-automation/actions/runs/39005846380): completed with the expected configuration error. [Sanitized evidence](../examples/evidence/hosted-failure.json) records selected SHA `c68b702642032f4f44860ec82befa2e65b94c9fb`; [diagnosis](../examples/evidence/hosted-diagnosis.json) cites log line 5 and proposes no patch from logs alone.
- Initial hosted validation stopped at checksum verification for the reused unpacked Linux provider. Registry-verified Linux content hashes were added to all root lockfiles; checksum verification remains enabled.
- [Reusable hosted diagnosis run 39005957486](https://github.com/Shrinidhikulkarni7/intelligent-automation/actions/runs/39005957486): succeeded, including bounded collection, diagnosis and workflow-summary reporting.
