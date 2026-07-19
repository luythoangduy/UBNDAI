"""Xuất nhật ký sử dụng AI từ transcript Claude Code sang .ai-log/session.jsonl.

Vì sao cần script này: hook `scripts/log_hook.py` ghi log theo thời gian thực,
nhưng nó chưa từng được bật cho repo này nên `.ai-log/` trống. Transcript đầy đủ
vẫn còn trong `~/.claude/projects/<slug>/*.jsonl`, nên log dựng lại được sau.
Định dạng đầu ra khớp đúng schema mà log_hook.py sinh, để hai nguồn trộn được.

⚠ CHE SECRET LÀ BẮT BUỘC, KHÔNG PHẢI TUỲ CHỌN.
Transcript ghi lại nguyên văn mọi thứ đã hiện trên màn hình, gồm cả output của
những lệnh vô tình in ra API key. Phiên 19/07/2026 có đúng trường hợp đó. Vì vậy
mọi giá trị đi qua `redact()` trước khi ghi. Không tắt được bằng cờ dòng lệnh —
nếu cần bản thô thì đọc thẳng transcript gốc.

Chạy:
    python scripts/export_ai_log.py                 # ghi .ai-log/session.jsonl
    python scripts/export_ai_log.py --stdout        # in ra màn hình
    python scripts/export_ai_log.py --out FILE
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterator

MAX_PROMPT = 4000
MAX_TOOL_INPUT = 2000
MAX_TOOL_RESPONSE = 2000

# Che theo hình dạng khoá, không theo tên biến: một khoá bị in ra giữa output
# của lệnh khác sẽ không có nhãn "API_KEY=" đứng trước.
SECRET_PATTERNS = [
    re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{32,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    re.compile(r"hf_[A-Za-z0-9]{30,}"),
    # Dạng gán tên=giá trị, bắt phần đuôi mà các mẫu trên bỏ sót.
    re.compile(
        r"(?i)\b((?:api[_-]?key|access[_-]?token|secret|password|passwd|bearer)"
        r"\s*[=:]\s*)(['\"]?)([^\s'\"]{12,})",
    ),
]


def redact(text: str) -> str:
    if not text:
        return text
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 3:
            text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}<đã che>", text)
        else:
            text = pattern.sub("<đã che>", text)
    return text


def git(cmd: str) -> str:
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return ""


def clip(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = redact(text)
    return text if len(text) <= limit else text[:limit] + f"…(cắt bớt, tổng {len(text)})"


def text_of(content: Any) -> str:
    """Gộp phần text của một message; bỏ khối thinking (nội bộ, không phải log dùng)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(p for p in parts if p)


def transcripts(project_dir: Path) -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(project_dir / "*.jsonl")))


def convert(path: Path, meta: dict[str, str]) -> Iterator[dict[str, Any]]:
    """Sinh entry theo schema của log_hook.py từ một transcript."""
    # tool_use_id -> tên tool, để ghép tool_result (nằm ở record `user` kế tiếp).
    pending: dict[str, tuple[str, str]] = {}

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            kind = record.get("type")
            if kind not in ("user", "assistant"):
                continue

            base = {
                "ts": record.get("timestamp", ""),
                "tool": "claude",
                "event": "",
                "session_id": record.get("sessionId", ""),
                "model": (record.get("message") or {}).get("model", ""),
                "repo": meta["repo"],
                "branch": record.get("gitBranch") or meta["branch"],
                "commit": meta["commit"],
                "student": meta["student"],
                "prompt": "",
                "tool_name": "",
                "tool_input": "",
                "tool_response": "",
            }
            content = (record.get("message") or {}).get("content")

            if kind == "user":
                # Record `user` mang hai thứ rất khác nhau: prompt thật của người
                # dùng, và kết quả tool do harness chèn vào. Tách ra, nếu không
                # log sẽ báo cáo output của máy như thể người dùng gõ.
                results = [
                    b for b in content
                    if isinstance(b, dict) and b.get("type") == "tool_result"
                ] if isinstance(content, list) else []

                for block in results:
                    name, args = pending.pop(block.get("tool_use_id", ""), ("", ""))
                    yield {
                        **base,
                        "event": "PostToolUse",
                        "tool_name": name,
                        "tool_input": args,
                        "tool_response": clip(block.get("content", ""), MAX_TOOL_RESPONSE),
                    }

                if record.get("isMeta"):
                    continue
                prompt = text_of(content)
                if prompt.strip():
                    yield {**base, "event": "UserPromptSubmit", "prompt": clip(prompt, MAX_PROMPT)}

            else:
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            pending[block.get("id", "")] = (
                                block.get("name", ""),
                                clip(block.get("input", {}), MAX_TOOL_INPUT),
                            )
                answer = text_of(content)
                if answer.strip():
                    yield {
                        **base,
                        "event": "Stop",
                        "tool_response": clip(answer, MAX_TOOL_RESPONSE),
                    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", default="", help="thư mục transcript Claude Code")
    parser.add_argument("--out", default="", help="đường dẫn file đầu ra")
    parser.add_argument("--stdout", action="store_true", help="in ra màn hình thay vì ghi file")
    args = parser.parse_args()

    project_dir = Path(
        args.project_dir
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or Path.home() / ".claude" / "projects" / "C--AI-Chalenge"
    )
    if not project_dir.is_dir():
        raise SystemExit(f"Không thấy thư mục transcript: {project_dir}")

    meta = {
        "repo": Path(git("git rev-parse --show-toplevel") or ".").name,
        "branch": git("git rev-parse --abbrev-ref HEAD"),
        "commit": git("git rev-parse --short HEAD"),
        "student": git("git config user.email"),
    }

    files = transcripts(project_dir)
    if not files:
        raise SystemExit(f"Không có transcript nào trong {project_dir}")

    entries = [entry for path in files for entry in convert(path, meta)]
    entries.sort(key=lambda e: e["ts"])

    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    if args.stdout:
        print("\n".join(lines))
        return

    out = Path(args.out) if args.out else Path(".ai-log") / "session.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    by_event: dict[str, int] = {}
    for entry in entries:
        by_event[entry["event"]] = by_event.get(entry["event"], 0) + 1
    print(f"Đã ghi {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  transcript đọc : {len(files)}")
    print(f"  entry          : {len(entries)}  {by_event}")
    print(f"  phiên           : {len({e['session_id'] for e in entries})}")


if __name__ == "__main__":
    main()
