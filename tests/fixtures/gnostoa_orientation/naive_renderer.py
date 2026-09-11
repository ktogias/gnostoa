"""Constructed D14-O1 baseline: it erases conflicting selections."""

import json
import sys

snapshot = json.load(sys.stdin)
current = snapshot["facts"]["current"]
selected = current[0]["text"] if current else "No selected work item."
print(json.dumps({"status": "CURRENT", "current": selected}, sort_keys=True))
