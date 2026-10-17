"""Proposal bundles and idempotent branch / PR publication."""
import json
from pathlib import Path
import re
import shutil
import tempfile
from .adapter import Limits, generate
from .core import ROOT, TARGET, Rejected, canonical, config, digest, lock, proposal, read_json, request, summary, target
from .process import run


def build(req, out, *, adapter, fixture=None, limits=Limits(), current_path=None):
    req = request(req)
    current_file = Path(current_path or ROOT / target(req))
    current = config(read_json(current_file)) if current_file.exists() else {}
    if req["operation"] == "retention" and not current:
        raise Rejected("existing managed configuration is missing")
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    with lock(directory / "locks"):
        result, provenance = generate(req, current, adapter=adapter, fixture=fixture, limits=limits)
        value = proposal(result, req, current)
        key = "dev-app-" + req["operation"]
        report = {"request": req, "request_digest": digest(req), "proposal_digest": digest(value),
                  "base_digest": digest(current), "branch": f"proposal/{key}", "provenance": provenance,
                  "assumptions": result["assumptions"], "required_inputs": result["required_inputs"],
                  "diagnostics": result["diagnostics"], "summary": summary(req, current, value)}
        bundle = directory / key
        # Stage and replace files only after every check passed.
        bundle.mkdir(exist_ok=True)
        (bundle / "main.tf.json").write_text(canonical(value))
        (bundle / "report.json").write_text(canonical(report))
        (bundle / "pr.md").write_text(pr_body(report))
        return bundle, report


def pr_body(report):
    s = report["summary"]
    return (f"Propose {s['operation']} for {s['target']}.\n\n"
            f"Retention days: {s['retention_days']['before']} → {s['retention_days']['after']}. "
            "Reviewed module supplies encryption, public-access blocks and lifecycle expiration.\n\n"
            f"Adapter: {report['provenance']['adapter']}; live AI: {report['provenance']['live']}. "
            "No cloud execution performed.\n\n"
            "Assumptions:\n" + "".join(f"- {item}\n" for item in report['assumptions']) +
            "\nValidation required: Python checks, Terraform fmt/validate and mocked-provider tests. "
            "New resources require infrastructure review. Reducing expiration may delete existing objects earlier.\n\n"
            f"Proposal digest: `{report['proposal_digest']}`. Execute only an explicitly reviewed, merged revision.\n")


def checked(argv, cwd, **kwargs):
    code, stdout, _ = run(argv, cwd=cwd, **kwargs)
    if code:
        raise Rejected(f"{argv[0]} operation failed; inspect locally without publishing raw output")
    return stdout.strip()


def publish(bundle, repo, *, source=ROOT, remote=False):
    """Use an isolated clone; never run generated files or change the caller's checkout."""
    bundle = Path(bundle).resolve()
    report = read_json(bundle / "report.json")
    req = request(report["request"])
    value = config(read_json(bundle / "main.tf.json"), req["retention_days"])
    if digest(value) != report["proposal_digest"] or report["branch"] != f"proposal/dev-app-{req['operation']}":
        raise Rejected("bundle integrity mismatch")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise Rejected("expected public GitHub owner/repository")
    with lock(bundle.parent / "locks"):
        with tempfile.TemporaryDirectory(prefix="reviewed-publish-") as folder:
            clone = Path(folder) / "repo"
            checked(["git", "clone", "--quiet", "--no-hardlinks", str(source), str(clone)], ROOT)
            path = target(req)
            code, base, _ = run(["git", "show", f"HEAD:{path}"], cwd=clone)
            current = config(json.loads(base)) if code == 0 else {}
            if req["operation"] == "retention" and not current:
                raise Rejected("existing configuration missing")
            if digest(current) != report["base_digest"]:
                raise Rejected("base configuration changed; regenerate proposal")
            # Recheck the full retention-only invariant at publication.
            proposal({"status":"proposed", "terraform":canonical(value), "assumptions":[], "required_inputs":[], "diagnostics":[]}, req, current)
            branch = report["branch"]
            checked(["git", "checkout", "-B", branch], clone)
            (clone / path).write_text(canonical(value))
            checked(["git", "add", "--", path], clone)
            if not checked(["git", "diff", "--cached", "--name-only"], clone):
                return {"status": "already_satisfied", "branch": branch}
            checked(["git", "config", "user.name", "Reviewed DevOps"], clone)
            checked(["git", "config", "user.email", "reviewed-devops@users.noreply.github.com"], clone)
            checked(["git", "add", "--", path], clone)
            checked(["git", "commit", "--quiet", "-m", f"Propose {req['operation']} for {report['summary']['target']}"], clone)
            sha = checked(["git", "rev-parse", "HEAD"], clone)
            if not remote:
                destination = bundle / "branch.bundle"
                checked(["git", "bundle", "create", str(destination), branch], clone)
                return {"status":"local_branch", "branch":branch, "revision":sha, "bundle":"branch.bundle", "pr":"not published"}
            visibility = checked(["gh", "api", f"repos/{repo}", "--jq", ".private"], clone)
            if visibility != "false":
                raise Rejected("publication requires an accessible public repository")
            checked(["git", "remote", "set-url", "origin", f"https://github.com/{repo}.git"], clone)
            checked(["git", "fetch", "origin", "main"], clone)
            if checked(["git", "rev-parse", "origin/main"], clone) != checked(["git", "rev-parse", "HEAD^"], clone):
                raise Rejected("remote main differs; update trusted checkout and regenerate")
            # Resolve an existing proposal by target+operation, not by the text's hash.
            prs = json.loads(checked(["gh", "pr", "list", "--repo", repo, "--head", branch, "--state", "open", "--json", "number,url"], clone))
            # Read remote ref first, then bind a lease so racing publishers cannot overwrite it.
            refs = checked(["git", "ls-remote", "origin", f"refs/heads/{branch}"], clone)
            old = refs.split()[0] if refs else ""
            if old and prs:
                checked(["git", "fetch", "origin", f"refs/heads/{branch}"], clone)
                code, content, _ = run(["git", "show", f"FETCH_HEAD:{path}"], cwd=clone)
                changed = checked(["git", "diff", "--name-only", "origin/main...FETCH_HEAD"], clone).splitlines()
                if set(changed) - {path}:
                    raise Rejected("existing proposal contains unrelated edits; manual reconciliation required")
                if code == 0 and json.loads(content) == value:
                    return {"status":"existing_pull_request", "branch":branch, "revision":old, "url":prs[0]["url"]}
            checked(["git", "push", "origin", f"HEAD:refs/heads/{branch}", f"--force-with-lease=refs/heads/{branch}:{old}"], clone)
            body = clone / "pr-body.md"
            body.write_text(pr_body(report))
            if prs:
                checked(["gh", "pr", "edit", str(prs[0]["number"]), "--repo", repo, "--body-file", str(body)], clone)
                url = prs[0]["url"]
            else:
                url = checked(["gh", "pr", "create", "--repo", repo, "--base", "main", "--head", branch, "--title", f"Propose {req['operation']} for {report['summary']['target']}", "--body-file", str(body)], clone)
            return {"status":"pull_request", "branch":branch, "revision":sha, "url":url,
                    "validation":"inspect PR checks; automation token event behavior depends on token type and GitHub version"}
