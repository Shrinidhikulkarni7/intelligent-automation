"""Optional real-cloud path. No default cloud calls; no plan/state publication."""
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from .core import ROOT, Rejected, canonical, config, digest, lock, read_json
from .process import run
from .proposals import checked

TYPES = {"aws_s3_bucket", "aws_s3_bucket_public_access_block", "aws_s3_bucket_server_side_encryption_configuration", "aws_s3_bucket_ownership_controls", "aws_s3_bucket_lifecycle_configuration"}
TARGETS = {"dev/app":"infra/environments/dev", "dev/new-app":"infra/environments/dev-new"}


def plan_summary(plan):
    changes = []
    for change in plan.get("resource_changes", []):
        actions = change["change"]["actions"]
        if actions == ["no-op"]:
            continue
        if change.get("mode") != "managed" or change["type"] not in TYPES or not re.fullmatch(r"module\.app\.aws_s3_[a-z_]+\.app", change["address"]) or actions not in (["create"], ["update"]):
            raise Rejected("plan contains deletion, replacement, unapproved resource or action; additional review required")
        changes.append({"address":change["address"], "actions":actions})
    return {"resource_changes":changes, "destruction_permitted":False}


def execute(*, revision, target, action, backend, authorization, expected_plan=None, out=".out/cloud-report.json"):
    if target not in TARGETS or action not in ("plan", "apply") or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise Rejected("explicit allowed target, action and full reviewed revision required")
    if authorization != f"{action}:{target}:{revision}":
        raise Rejected("explicit authorization must bind action, target and reviewed revision")
    if os.environ.get("REVIEWED_DEVOPS_LIVE") != "enabled":
        raise Rejected("real-cloud integration not configured; no cloud calls made")
    backend = Path(backend).resolve()
    text = backend.read_text()
    # Closed backend format: no credentials, endpoint overrides or disabled locking.
    pairs = dict(re.findall(r'^([a-z_]+)\s*=\s*("[^"\n]+"|true)\s*$', text, re.M))
    if set(pairs) != {"bucket", "key", "region", "encrypt", "use_lockfile"} or pairs["encrypt"] != "true" or pairs["use_lockfile"] != "true":
        raise Rejected("encrypted S3 remote backend with lockfile required")
    if any(line.strip() and not line.lstrip().startswith("#") and not re.fullmatch(r'[a-z_]+\s*=\s*("[^"\n]+"|true)\s*', line) for line in text.splitlines()):
        raise Rejected("backend contains unsupported configuration")
    expected_key = '"reviewed-devops/' + target + '.tfstate"'
    if pairs["key"] != expected_key or not re.fullmatch(r'"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]"', pairs["bucket"]) or pairs["region"] != '"us-east-1"':
        raise Rejected("backend does not match explicit target or region")
    # Reviewed revision must be merged into locally fetched origin/main. Caller must fetch it freshly.
    checked(["git", "merge-base", "--is-ancestor", revision, "origin/main"], ROOT)
    report_path = Path(out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    status = {"target":target, "revision":revision, "action":action, "status":"started", "cloud_execution":"outcome uncertain until completion"}
    report_path.write_text(canonical(status))
    with lock(ROOT / ".out/locks"):
        with tempfile.TemporaryDirectory(prefix="reviewed-cloud-") as folder:
            workspace = Path(folder)
            # Extract only known files from reviewed revision, with no shell or archive traversal.
            paths = [TARGETS[target] + "/main.tf.json", TARGETS[target] + "/versions.tf", TARGETS[target] + "/.terraform.lock.hcl", "infra/modules/private_bucket/main.tf"]
            for path in paths:
                content = checked(["git", "show", f"{revision}:{path}"], ROOT)
                dest = workspace / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content + "\n")
            cwd = workspace / TARGETS[target]
            value = config(read_json(cwd / "main.tf.json"))
            (cwd / "backend.tf").write_text('terraform {\n  backend "s3" {}\n}\n')
            env = {k:v for k,v in os.environ.items() if k in ("PATH","HOME","TMPDIR","AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY","AWS_SESSION_TOKEN","AWS_REGION","AWS_DEFAULT_REGION","SSL_CERT_FILE")}
            env.update(TF_IN_AUTOMATION="1", AWS_EC2_METADATA_DISABLED="true")
            def tf(*args):
                return checked(["terraform", *args], cwd, timeout=300, limit=2_000_000, env=env)
            try:
                tf("init", "-input=false", "-lockfile=readonly", f"-backend-config={backend}")
                tf("validate")
                tf("plan", "-input=false", "-lock-timeout=60s", "-out=review.tfplan")
                plan = json.loads(tf("show", "-json", "review.tfplan"))
                result = plan_summary(plan)
                plan.pop("timestamp", None)
                fingerprint = digest(plan)
                status.update(result, plan_digest=fingerprint, configuration_digest=digest(value), status="planned", cloud_execution="plan completed; providers and backend accessed")
                report_path.write_text(canonical(status))
                if action == "apply":
                    if expected_plan != fingerprint:
                        raise Rejected("plan changed or no reviewed plan digest supplied; run plan and review again")
                    tf("apply", "-input=false", "review.tfplan")
                    code, _, _ = run(["terraform", "plan", "-input=false", "-detailed-exitcode", "-lock-timeout=60s"], cwd=cwd, env=env, timeout=300, limit=2_000_000)
                    if code != 0:
                        raise Rejected("post-apply verification failed or drift remains; investigate partial completion")
                    status.update(status="verified", cloud_execution="apply completed; follow-up provider plan reports no changes")
                    report_path.write_text(canonical(status))
            except Exception:
                status.update(status="incomplete", cloud_execution="operation stopped; cloud state may have changed; no rollback or cleanup attempted")
                report_path.write_text(canonical(status))
                raise
    return status
