"""Evidence-linked deterministic diagnosis; unknown errors yield no patch."""
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from .core import ROOT, Rejected, canonical, read_json
from .process import run

MAX_LOG = 24_000


def sanitize(raw):
    raw = re.sub(r"(?:\x1b|\^\[)\[[0-9;]*[A-Za-z]", "", raw)
    raw = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[KEY REDACTED]", raw, flags=re.S)
    raw = re.sub(r"(?i)(?:Bearer\s+\S+|(?:[A-Za-z0-9_]*(?:token|password|secret|api[_-]?key|access[_-]?key)[A-Za-z0-9_-]*)\s*[:=]\s*\S+|AKIA[A-Z0-9]{16}|github_pat_[A-Za-z0-9_]{15,}|gh[pousr]_[A-Za-z0-9_]{15,})", "[REDACTED]", raw)
    raw = re.sub(r"https?://\S+", "[URL REDACTED]", raw)
    raw = re.sub(r"(?:/Users|/home)/[^\s:]+", "[PATH REDACTED]", raw)
    return "\n".join(line[:1000] for line in raw.splitlines()[:200])


def collect_local(out):
    """Reproduce the same step as intentional-failure.yml, not a hosted run."""
    code, stdout, stderr = run(["python3", "examples/failing_check.py"], cwd=ROOT, env={"PATH": __import__('os').environ.get('PATH', '')}, limit=MAX_LOG)
    evidence = {"source":"local-reproduction", "workflow":"intentional-failure.yml", "revision":"working-tree",
                "stage":"configuration-check", "conclusion":"failure" if code else "success", "exit_code":code,
                "logs":sanitize(stdout+stderr)}
    Path(out).write_text(canonical(evidence))
    return evidence


def collect_github(repo, run_id, out):
    """Fetch bounded selected public-run metadata and failed job logs with gh."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not re.fullmatch(r"[1-9][0-9]{0,19}", str(run_id)):
        raise Rejected("invalid public repository or run id")
    code, raw, _ = run(["gh", "api", f"repos/{repo}"], limit=24_000)
    if code or json.loads(raw).get("private") is not False:
        raise Rejected("only accessible public repositories are permitted")
    code, raw, _ = run(["gh", "run", "view", str(run_id), "--repo", repo, "--json", "conclusion,headSha,workflowName,jobs"], limit=48_000)
    if code:
        raise Rejected("workflow evidence unavailable; integration not configured or run missing")
    meta = json.loads(raw)
    if meta["conclusion"] != "failure":
        raise Rejected("selected run is not a completed failure")
    failed = [job for job in meta["jobs"] if job["conclusion"] == "failure"]
    if len(failed) != 1:
        raise Rejected("select a run with one failed job; ambiguous evidence")
    job = failed[0]
    code, logs, _ = run(["gh", "run", "view", str(run_id), "--repo", repo, "--job", str(job["databaseId"]), "--log-failed"], limit=MAX_LOG)
    if code:
        raise Rejected("bounded logs unavailable; no diagnosis inferred")
    value = {"source":"github-run", "repository":repo, "run_id":str(run_id), "revision":meta["headSha"],
             "workflow":sanitize(meta["workflowName"]), "stage":sanitize(job["name"]), "conclusion":"failure", "logs":sanitize(logs)}
    Path(out).write_text(canonical(value))
    return value


def diagnose(evidence):
    allowed = {"source", "workflow", "revision", "stage", "conclusion", "exit_code", "logs", "repository", "run_id"}
    if not isinstance(evidence, dict) or set(evidence) - allowed or not {"source","workflow","revision","stage","conclusion","logs"} <= set(evidence):
        raise Rejected("invalid evidence structure")
    if len(canonical(evidence).encode()) > 48_000 or not isinstance(evidence["logs"], str):
        raise Rejected("evidence too large or malformed")
    logs = sanitize(evidence["logs"])
    lines = logs.splitlines()
    marker = "CONFIG_ERROR: DEMO_REGION must equal us-east-1"
    refs = [f"sanitized-log:L{i}" for i, line in enumerate(lines, 1) if marker in line]
    result = {"source":evidence["source"], "revision":sanitize(str(evidence["revision"])),
              "failed_stage":sanitize(str(evidence["stage"])), "evidence_digest":hashlib.sha256(logs.encode()).hexdigest(),
              "sanitized_log":logs, "confirmed":[], "suspected":[], "missing_evidence":[], "next_check":"Inspect the exact failed step and its inputs at the selected revision.", "proposed_patch":None}
    if refs and evidence["conclusion"] == "failure":
        result["confirmed"] = [{"finding":"The configuration check reported an absent or unequal DEMO_REGION.", "evidence":refs}]
        result["suspected"] = ["The step environment may omit DEMO_REGION; the log alone cannot distinguish missing from unequal."]
        result["missing_evidence"] = ["The selected workflow file and environment at that run's revision."]
        result["next_check"] = "Read intentional-failure.yml and failing_check.py at the selected revision; verify the step environment."
        # Only the local reproduction has a trusted, current workflow and script to corroborate a fix.
        workflow = ROOT / ".github/workflows/intentional-failure.yml"
        if evidence["source"] == "local-reproduction" and evidence.get("exit_code") == 2 and logs.strip() == marker and workflow.exists():
            text = workflow.read_text()
            if "run: python3 examples/failing_check.py" in text and "DEMO_REGION" not in text:
                result["confirmed"].append({"finding":"The inspected local workflow omits DEMO_REGION; the local reproduction exited 2.", "evidence":[".github/workflows/intentional-failure.yml", "examples/failing_check.py", *refs]})
                result["missing_evidence"] = ["No hosted workflow run was inspected in this local reproduction."]
                patched = text.replace("        run: python3 examples/failing_check.py", "        env:\n          DEMO_REGION: us-east-1\n        run: python3 examples/failing_check.py", 1)
                diff = "".join(difflib.unified_diff(text.splitlines(keepends=True), patched.splitlines(keepends=True), fromfile="a/.github/workflows/intentional-failure.yml", tofile="b/.github/workflows/intentional-failure.yml"))
                result["proposed_patch"] = {"unified_diff":diff, "path":".github/workflows/intentional-failure.yml", "change":"Set env: {DEMO_REGION: us-east-1} on the configuration-check step.", "automatic_application":False}
    else:
        result["missing_evidence"] = ["A recognized error and corroborating configuration; no justified patch."]
    return result
