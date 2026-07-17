"""Discover and incrementally sync official procedure pages.

Example:
  python scripts/sync_procedures.py --index-url https://dichvucong.gov.vn/p/home/dvc-tthc.html
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from src.services.sources import DvcNationalConnector, sync_connector  # noqa: E402


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-url", action="append", required=True)
    parser.add_argument("--allowed-domain", action="append", default=[])
    parser.add_argument("--rate-limit", type=float, default=0.5)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument(
        "--index-dense",
        action="store_true",
        help="Upsert đúng các section thay đổi vào Chroma; cần embedding đã cấu hình",
    )
    args = parser.parse_args()
    allowed = set(args.allowed_domain) or None
    connector = DvcNationalConnector(
        args.index_url,
        allowed_domains=allowed,
        rate_limit_seconds=args.rate_limit,
    )
    result = await sync_connector(
        connector,
        run_llm=not args.no_llm,
        index_dense=args.index_dense,
    )
    print(result.model_dump_json(indent=2))
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
