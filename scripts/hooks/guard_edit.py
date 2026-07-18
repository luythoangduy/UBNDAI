#!/usr/bin/env python3
"""PreToolUse guard for Edit|Write: block edits to secrets/VCS-internal files.

Reads the tool call JSON from stdin. Exit 2 (+ stderr message) blocks the
edit; exit 0 allows it. Must never raise — a bug here should not block work.
"""
import json
import re
import sys

PROTECTED = re.compile(r"(^|[\\/])\.env(\.|$)|[\\/]\.git[\\/]|(^|[\\/])secrets[\\/]")


def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    path = (data.get("tool_input") or {}).get("file_path", "")
    if PROTECTED.search(path):
        print(f"Blocked: '{path}' looks like a protected file (.env / .git / secrets/).", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
