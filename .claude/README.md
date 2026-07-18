# Claude Code harness — TTHC Assist

Same pattern as the TripNest AI (`C2-App-031`) repo: safety hooks + a
cross-tool session logger. Skills themselves (`/spec`, `/plan`, `/build`,
`/test`, `/review`, `/code-simplify`, `/ship`, etc.) come from the
`agent-skills` plugin marketplace, already enabled globally for this user —
no per-project copy needed for Claude Code.

## Active hooks (`settings.json`)

**PreToolUse**
- `guard_edit.py` — blocks Edit/Write on `.env`, `.git/`, `secrets/`.
- `guard_bash.py` — blocks `rm -rf /`, `DROP DATABASE`, `TRUNCATE TABLE`, `git push --force`.

**PostToolUse**
- `format_on_save.py` — `ruff format` on edited `.py` files; `prettier` on
  frontend `.ts/.tsx/.js/.jsx` if `frontend/node_modules/.bin/prettier` exists
  (not currently installed — no-ops until it is).
- `log_hook.py` — appends a normalized entry to `.ai-log/session.jsonl`
  (gitignored). Same logger as TripNest; also understands Gemini CLI, Codex,
  Cursor, Copilot if this repo is ever opened with those tools.

**Stop**
- `session_summary.py` — prints `git status` reminder to review before
  committing (branch + push, no PR — see `AGENTS.md` / memory).
- `log_hook.py` — also appends changed files to `WORKLOG.md` under today's
  date, *if* a `WORKLOG.md` file already exists at repo root. It doesn't yet
  in this repo — create one (copy TripNest's format) if the team wants that.

## Permissions (`settings.json`)

Baseline allow-list for this repo's known commands (`pytest`, `ruff`,
`alembic`, `uvicorn src.main:app`, `git checkout/add/commit/push`, `npm`).
Personal one-off grants accumulate in `settings.local.json` (gitignored) as
you work — don't hand-edit that file.

## Not replicated from TripNest

- `.agents/skills` + `.claude/skills` symlink farm: that exists there for
  cross-tool portability (Cursor/Gemini/Codex don't share Claude's plugin
  marketplace). Skip unless this repo is also driven by those tools.
- The `harness-cli` binary / `harness.db`: a separate personal tool, not part
  of this bundle.
