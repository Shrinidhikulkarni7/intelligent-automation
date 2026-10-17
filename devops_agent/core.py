"""Small, deliberately closed proposal language. No evaluation of model code."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET = "infra/environments/dev/main.tf.json"
CREATE_TARGET = "infra/environments/dev-new/main.tf.json"


def target(req):
    return CREATE_TARGET if req["operation"] == "create" else TARGET


MODULE = "../../modules/private_bucket"
MAX_BYTES = 48_000


class Rejected(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path, limit=MAX_BYTES):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise Rejected("input exceeds byte limit")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Rejected("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise Rejected("unexpected or missing fields")


def safe_text(text, limit=1000):
    if not isinstance(text, str) or len(text) > limit or any(ord(c) < 32 and c != '\n' for c in text):
        raise Rejected("invalid text")
    # Defense in depth; not a general secret detector. Only public input is allowed.
    if re.search(r"(?i)(AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9_]{15,}|-----BEGIN .*PRIVATE KEY|(?:token|password|secret|api_key)\s*[:=]\s*\S+|https?://)", text):
        raise Rejected("possible credential or URL: use public, secret-free input")
    return text


def request(value):
    exact(value, ("version", "operation", "environment", "resource", "retention_days", "text"))
    if value["version"] != 1 or type(value["version"]) is not int:
        raise Rejected("unsupported request version")
    if value["operation"] not in ("create", "retention") or value["environment"] != "dev" or value["resource"] != "app":
        raise Rejected("unsupported scope; only dev/app create or retention is supported")
    if type(value["retention_days"]) is not int or not 1 <= value["retention_days"] <= 30:
        raise Rejected("retention_days must be an integer from 1 to 30")
    safe_text(value["text"])
    return value


def parse_text(text):
    """Explicit narrow grammar; ambiguous requests are never silently guessed."""
    safe_text(text)
    create = re.fullmatch(r"Create a private object-storage bucket for a development application, with encryption, public access blocked, and a (\d+)-day lifecycle policy\.?", text, re.I)
    update = re.fullmatch(r"Change (?:this|the) development resource's retention period from seven days to (three|\d+) days\.?", text, re.I)
    if not (create or update):
        raise Rejected("unsupported or incomplete natural-language request; specify a 1–30 day lifecycle or use the structured request format")
    days = create[1] if create else ("3" if update[1].lower() == "three" else update[1])
    return request(dict(version=1, operation="create" if create else "retention", environment="dev", resource="app", retention_days=int(days), text=text))


def config(value, days=None):
    if not isinstance(value, dict) or "module" not in value or set(value) - {"module", "locals", "output"}:
        raise Rejected("only approved module, literal label locals and bucket_id output are permitted")
    exact(value["module"], ("app",))
    args = value["module"]["app"]
    exact(args, ("source", "bucket_name", "retention_days", "tags"))
    if args["source"] != MODULE or args["bucket_name"] not in ("reviewed-devops-example-app", "reviewed-devops-example-new-app"):
        raise Rejected("module source or bucket identity outside permitted scope")
    if type(args["retention_days"]) is not int or not 1 <= args["retention_days"] <= 30:
        raise Rejected("unsafe retention")
    if days is not None and args["retention_days"] != days:
        raise Rejected("proposal does not match requested retention")
    tags = args["tags"]
    if "locals" in value:
        exact(value["locals"], ("labels",))
        if tags != "${local.labels}":
            raise Rejected("locals may only supply module labels")
        tags = value["locals"]["labels"]
    if "output" in value:
        exact(value["output"], ("bucket_id",))
        exact(value["output"]["bucket_id"], ("value",))
        if value["output"]["bucket_id"]["value"] != "${module.app.bucket_id}":
            raise Rejected("only approved bucket_id output reference is allowed")
    if not isinstance(tags, dict) or len(tags) > 8 or tags.get("Environment") != "dev" or tags.get("ManagedBy") != "reviewed-devops":
        raise Rejected("required tags missing or too many tags")
    for key, val in tags.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,31}", key) or not isinstance(val, str) or not re.fullmatch(r"[A-Za-z0-9 ._-]{1,64}", val):
            raise Rejected("tags must be bounded literal public text")
    return value


def proposal(result, req, current):
    exact(result, ("status", "terraform", "assumptions", "required_inputs", "diagnostics"))
    for field in ("assumptions", "required_inputs", "diagnostics"):
        if not isinstance(result[field], list) or len(result[field]) > 8:
            raise Rejected("invalid diagnostic list")
        for item in result[field]:
            safe_text(item, 500)
    if result["status"] != "proposed":
        raise Rejected("agent declined or needs input: " + "; ".join(result["diagnostics"] + result["required_inputs"]))
    if result["required_inputs"]:
        raise Rejected("proposal has unresolved required inputs")
    if not isinstance(result["terraform"], str):
        raise Rejected("terraform must be a serialized Terraform JSON document")
    value = config(json.loads(result["terraform"]), req["retention_days"])
    expected_name = "reviewed-devops-example-new-app" if req["operation"] == "create" else "reviewed-devops-example-app"
    if value["module"]["app"]["bucket_name"] != expected_name:
        raise Rejected("bucket identity does not match operation")
    if req["operation"] == "retention":
        config(current)
        before, after = json.loads(canonical(current)), json.loads(canonical(value))
        before["module"]["app"]["retention_days"] = after["module"]["app"]["retention_days"]
        if before != after:
            raise Rejected("retention update changed unrelated configuration")
    return value


def summary(req, current, value):
    old = current["module"]["app"]["retention_days"] if req["operation"] == "retention" else None
    return {"target": "dev/new-app" if req["operation"] == "create" else "dev/app", "configuration_path": target(req), "operation": req["operation"],
            "retention_days": {"before": old, "after": value["module"]["app"]["retention_days"]},
            "controls": ["AES256 encryption", "four public-access blocks", "bucket-owner enforced", "prevent_destroy"],
            "cloud_execution": "not performed", "new_resources": req["operation"] == "create",
            "expected_resource_changes": (["aws_s3_bucket.app", "aws_s3_bucket_public_access_block.app", "aws_s3_bucket_server_side_encryption_configuration.app", "aws_s3_bucket_ownership_controls.app", "aws_s3_bucket_lifecycle_configuration.app"] if req["operation"] == "create" else ["aws_s3_bucket_lifecycle_configuration.app: expiration days only"])}


@contextmanager
def lock(directory, environment="dev"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{environment}.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Rejected("environment already has an active operation") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
