#!/usr/bin/env python3
"""PreToolUse guard for Bash: block obviously destructive commands.

Reads the tool call JSON from stdin. Exit 2 (+ stderr message) blocks the
command; exit 0 allows it. Must never raise — a bug here should not block work.
"""
import json
import re
import sys

DESTRUCTIVE = re.compile(
    r"rm\s+-rf\s+(/|~|\.\.)(\s|$)|DROP\s+(DATABASE|TABLE)|TRUNCATE\s+TABLE|git\s+push\s+.*--force(?!-with-lease)",
    re.IGNORECASE,
)


def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    command = (data.get("tool_input") or {}).get("command", "")
    if DESTRUCTIVE.search(command):
        print("Blocked: destructive command detected. Confirm manually if intended.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
