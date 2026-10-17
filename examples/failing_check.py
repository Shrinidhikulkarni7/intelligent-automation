"""Intentionally failing workflow step; no external dependencies or secrets."""
import os
import sys

if os.environ.get("DEMO_REGION") != "us-east-1":
    print("CONFIG_ERROR: DEMO_REGION must equal us-east-1", file=sys.stderr)
    sys.exit(2)
print("Configuration accepted")
