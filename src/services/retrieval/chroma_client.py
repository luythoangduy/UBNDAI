"""Chroma persistent client. Port nguyên vẹn từ C2-App-108/src/services/chroma_client.py."""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=16)
def get_chroma_persistent_client(persist_dir: str) -> Any | None:
    chromadb = _optional_import("chromadb")
    if chromadb is None:
        return None
    return chromadb.PersistentClient(path=str(Path(persist_dir)))


def _optional_import(module_name: str) -> Any | None:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None
