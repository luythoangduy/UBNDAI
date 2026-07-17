"""Load catalog thủ tục từ ``data/procedures/*.json``. Owner: Dev A.

Catalog là nguồn sự thật cho checklist và citation (AGENTS.md §5) —
mọi thông tin thủ tục trả cho người dân phải trace về đây, không lấy từ prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models import Procedure

DEFAULT_CATALOG_DIR = Path(__file__).resolve().parents[2] / "data" / "procedures"

_CACHE: dict[str, dict[str, Procedure]] = {}


def load_catalog(catalog_dir: Path | str | None = None) -> dict[str, Procedure]:
    directory = Path(catalog_dir) if catalog_dir else DEFAULT_CATALOG_DIR
    cache_key = str(directory.resolve())
    if cache_key not in _CACHE:
        catalog: dict[str, Procedure] = {}
        source_paths: dict[str, Path] = {}
        national_codes: dict[str, Path] = {}
        for path in sorted(directory.glob("*.json")):
            procedure = Procedure.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
            if procedure.id in catalog:
                raise ValueError(
                    f"Duplicate procedure id {procedure.id!r}: "
                    f"{source_paths[procedure.id]} và {path}"
                )
            if procedure.national_code and procedure.national_code in national_codes:
                raise ValueError(
                    f"Duplicate national_code {procedure.national_code!r}: "
                    f"{national_codes[procedure.national_code]} và {path}"
                )
            catalog[procedure.id] = procedure
            source_paths[procedure.id] = path
            if procedure.national_code:
                national_codes[procedure.national_code] = path
        _CACHE[cache_key] = catalog
    return _CACHE[cache_key]


def get_procedure(procedure_id: str | None) -> Procedure | None:
    if not procedure_id:
        return None
    return load_catalog().get(procedure_id)


def clear_cache() -> None:
    _CACHE.clear()
