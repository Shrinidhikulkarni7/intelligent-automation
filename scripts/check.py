#!/usr/bin/env python3
"""Credential-free verification. Provider download is public network I/O."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from devops_agent.core import ROOT, config, read_json, proposal, canonical
from devops_agent.proposals import build


def command(argv, cwd=ROOT, env=None):
    subprocess.run(argv, cwd=cwd, env=env, check=True, timeout=180)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terraform", action="store_true")
    args = parser.parse_args()
    command([sys.executable,"-m","unittest","discover","-s","tests","-v"])
    config(read_json(ROOT / "infra/environments/dev/main.tf.json"))
    new = ROOT / "infra/environments/dev-new/main.tf.json"
    if new.exists():
        config(read_json(new))
    with tempfile.TemporaryDirectory(prefix="reviewed-check-") as temp:
        base = Path(temp)
        for label, operation in (("create","create"),("retention","retention"),("live-create","create")):
            bundle, _ = build(read_json(ROOT / f"examples/requests/{operation}.json"),base/"bundles",adapter="fixture",fixture=ROOT/f"examples/fixtures/{operation}.json")
            if label == "live-create":
                bundle = ROOT/"examples/evidence/live-create"
                report = read_json(bundle/"report.json")
                proposal({"status":"proposed", "terraform":canonical(read_json(bundle/"main.tf.json")), "assumptions":[], "required_inputs":[], "diagnostics":[]},report["request"],{})
            if args.terraform:
                destination = base/label/"infra"
                shutil.copytree(ROOT/"infra",destination,ignore=shutil.ignore_patterns(".terraform","*.tfstate*","backend.hcl"))
                env_dir = destination/"environments"/("dev-new" if operation=="create" else "dev")
                shutil.copy2(bundle/"main.tf.json",env_dir/"main.tf.json")
                # Only public provider installation; no inherited cloud credentials or Terraform CLI overrides.
                env = {k:v for k,v in os.environ.items() if k in ("PATH","HOME","TMPDIR","SSL_CERT_FILE","HTTPS_PROXY","HTTP_PROXY","NO_PROXY")}
                env.update(TF_IN_AUTOMATION="1",AWS_EC2_METADATA_DISABLED="true")
                plugins = ROOT/"infra/modules/private_bucket/.terraform/providers"
                command(["terraform","init","-backend=false","-input=false","-lockfile=readonly",f"-plugin-dir={plugins}"],env_dir,env)
                command(["terraform","fmt","-check","-recursive"],destination,env)
                command(["terraform","validate"],env_dir,env)
                command(["terraform","test"],env_dir,env)
        if args.terraform:
            module=ROOT/"infra/modules/private_bucket"
            command(["terraform","fmt","-check","-recursive","infra"])
            command(["terraform","validate"],module,env)
            command(["terraform","test"],module,env)
    print("Credential-free checks passed; no real cloud provisioning was tested.")


if __name__ == "__main__":
    main()
