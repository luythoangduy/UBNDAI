#!/usr/bin/env python3
"""Stop hook: print a short reminder of what changed this session."""
import subprocess


def main() -> None:
    try:
        status = subprocess.check_output(["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return

    print("\n--- Session Summary ---")
    if status.strip():
        print("Modified files:")
        print(status)
        print("Remember: review changes before committing (branch + push, no PR — see AGENTS.md).")
    else:
        print("No uncommitted changes.")


if __name__ == "__main__":
    main()
