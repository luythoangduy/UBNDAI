#!/usr/bin/env python3
"""PostToolUse formatter for Edit|Write: auto-format the file just touched.

- .py            -> `ruff format` (repo dev dependency)
- .ts/.tsx/.jsx   -> `prettier` if frontend/node_modules/.bin/prettier exists

Reads the tool call JSON from stdin. Never fails the hook — formatting is
best-effort, so any error is swallowed.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    path = (data.get("tool_input") or {}).get("file_path", "")
    if not path:
        return

    p = Path(path)
    try:
        if p.suffix == ".py":
            subprocess.run(["ruff", "format", str(p)], cwd=REPO_ROOT, check=False, capture_output=True)
        elif p.suffix in (".ts", ".tsx", ".js", ".jsx"):
            prettier = REPO_ROOT / "frontend" / "node_modules" / ".bin" / "prettier"
            if prettier.exists():
                subprocess.run([str(prettier), "--write", str(p)], cwd=REPO_ROOT, check=False, capture_output=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
