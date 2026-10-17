# Agent adapter contract

`generate(request, current, adapter=..., limits=...)` returns `(structured_result, provenance)`. See [adapter.py](../devops_agent/adapter.py) and [policy](../devops_agent/core.py).

## Input

- Versioned request: operation (`create` / `retention`), environment (`dev`), logical resource (`app`), integer retention days (1–30), public descriptive text.
- Permitted context: the selected current managed configuration, or an empty object for creation. No broad repository scan, log archive, environment dump or credentials enters the prompt.
- Limits: attempt timeout 5–180 seconds; 1–2 attempts; combined output cap 1–48 KB; inference reasoning effort low/medium/high. Default: 90 seconds, one attempt, 48 KB, low effort. Authentication preflight has its own ten-second cap. The whole process group is killed on timeout/output overflow.

## Structured result

```json
{
  "status": "proposed",
  "terraform": "{\"module\": { ... complete Terraform JSON ... }}",
  "assumptions": [],
  "required_inputs": [],
  "diagnostics": []
}
```

`status` also allows `needs_input` and `unsupported`; those outcomes cannot create a proposal. `terraform` is a serialized JSON document so the agent can author structure; parsing and closed policy happen afterward. Unresolved required inputs stop publication. A syntactically valid schema response does not establish correctness.

The contract permits literal module inputs and, for creation, optional `locals.labels` referenced exactly by `${local.labels}` and an output referencing exactly `${module.app.bucket_id}`. This supports generated structure without accepting arbitrary executable expressions. The agent may propose additional review in diagnostics, but a resource/provider/module outside the allowlist is rejected. Extending that allowlist is a human-reviewed repository change.

Provenance identifies adapter, live vs fixture, attempt count and configured limits. Proposal reports preserve sanitized assumptions and diagnostics. `fixture` requires an explicit file; it is never a fallback when live calls fail.

## Verified integration: local Codex CLI

Tested with Codex CLI 0.163.0, using the owner's existing configured login. Install that version and authenticate with `codex login`, or supply your own `CODEX_API_KEY` as supported by the CLI. No credential is embedded in this repository.

```sh
python3 -m devops_agent.cli propose \
  --request examples/requests/generated-layout.json \
  --adapter codex --out .out/live --timeout 90 --attempts 1 \
  --output-bytes 48000 --reasoning low
```

The adapter calls `codex exec` with a JSON output schema, read-only sandbox, approval policy `never`, `--ignore-user-config`, `--ephemeral`, a temporary working directory, and an allowlisted process environment. Shell/exec, apps, plugins, sub-agents, code mode, browser/computer, image and web tools are explicitly disabled in the pinned CLI; host skill discovery is skipped. These settings were exercised in a live call. No cloud or GitHub credential is forwarded. Authentication and provider networking remain the CLI's responsibility.

These are practical inference controls, **not a hard token or monetary budget**. Codex CLI does not expose a verified per-call billing ceiling in this implementation. Use provider-side account limits; do not claim bounded cost from a timeout alone. Model/tool behavior is nondeterministic, and the local sandbox does not prove isolation from every host-readable file. A dedicated runner/account is recommended before adapting this pattern beyond public inputs.

Missing binary/authentication returns `integration not configured`; execution/schema failure returns an honest failure and creates no new proposal. Diagnostics deliberately avoid echoing raw agent stderr, which could contain sensitive context. Explicitly investigate locally when needed.

## Additional agents

Claude Code, other CLIs and direct model APIs are untested extension points. Implement the same function contract; allowlist the environment, bound subprocess/API I/O, disable execution permissions, validate the result, record provenance, and add failure tests. Do not rename a fixture into an adapter and describe it as a live integration.

The optional GitHub workflow uses an owner-supplied API key in a protected environment. That hosted credential mode is separate from the verified local login and is not claimed as tested merely because the local adapter passed.
