"""python -m devops_agent.cli --help"""
import argparse
import json
from pathlib import Path
import sys
from .adapter import Limits
from .core import Rejected, canonical, parse_text, read_json
from .diagnosis import collect_github, collect_local, diagnose
from .execution import execute
from .proposals import build, publish


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reviewable agent-assisted DevOps examples")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--request")
    source.add_argument("--text")
    p.add_argument("--adapter", choices=("fixture","codex"), required=True)
    p.add_argument("--fixture")
    p.add_argument("--out", default=".out")
    p.add_argument("--timeout", type=int, default=90)
    p.add_argument("--attempts", type=int, default=1)
    p.add_argument("--output-bytes", type=int, default=48_000)
    p.add_argument("--reasoning", choices=("low","medium","high"), default="low")
    p = sub.add_parser("publish")
    p.add_argument("bundle")
    p.add_argument("--repo", required=True)
    p.add_argument("--source", default=".")
    p.add_argument("--remote", action="store_true", help="Explicitly push branch and create/update a public GitHub PR")
    p = sub.add_parser("collect")
    p.add_argument("--run")
    p.add_argument("--repo")
    p.add_argument("--out", default=".out/evidence.json")
    p = sub.add_parser("diagnose")
    p.add_argument("evidence")
    p.add_argument("--out")
    p = sub.add_parser("execute")
    p.add_argument("--revision", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--action", required=True, choices=("plan","apply"))
    p.add_argument("--backend", required=True)
    p.add_argument("--authorization", required=True)
    p.add_argument("--expected-plan")
    p.add_argument("--out", default=".out/cloud-report.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "propose":
            req = read_json(args.request) if args.request else parse_text(args.text)
            bundle, report = build(req, args.out, adapter=args.adapter, fixture=args.fixture, limits=Limits(args.timeout,args.attempts,args.output_bytes,args.reasoning))
            result = {"bundle":str(bundle), **report}
        elif args.command == "publish":
            result = publish(args.bundle, args.repo, source=args.source, remote=args.remote)
        elif args.command == "collect":
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            if bool(args.run) != bool(args.repo):
                raise Rejected("--repo and --run must be supplied together")
            result = collect_github(args.repo,args.run,args.out) if args.run else collect_local(args.out)
        elif args.command == "diagnose":
            result = diagnose(read_json(args.evidence))
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(canonical(result))
        else:
            result = execute(revision=args.revision,target=args.target,action=args.action,backend=args.backend,authorization=args.authorization,expected_plan=args.expected_plan,out=args.out)
        print(canonical(result),end="")
        return 0
    except (Rejected, OSError, ValueError, KeyError, TypeError) as error:
        # External command output, prompts, plans and credentials never appear in errors.
        message = str(error) if isinstance(error, Rejected) else "invalid input or unavailable local dependency; no successful completion claimed"
        print(canonical({"status":"rejected", "diagnostic":message}), file=sys.stderr,end="")
        return 2


if __name__ == "__main__":
    sys.exit(main())
