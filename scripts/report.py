"""Report a known sanitized report only; never glob for plans/state/logs."""
import json
import os
from pathlib import Path
import sys

path = Path(sys.argv[1])
if path.exists():
    value = json.loads(path.read_text())
    text = '```json\n' + json.dumps(value,indent=2,sort_keys=True) + '\n```\n'
else:
    text = 'No execution report exists; the operation did not reach the execution command.\n'
if 'GITHUB_STEP_SUMMARY' in os.environ:
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as stream:
        stream.write(text)
else:
    print(text)
