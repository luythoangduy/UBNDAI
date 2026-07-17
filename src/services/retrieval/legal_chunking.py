"""Chunker ``legal_hybrid`` tương thích pipeline VBPL của C2.

Giữ Markdown/line break để nhận ra Chương, Mục, Điều, Khoản, Điểm. Văn bản có
cấu trúc được chia theo đơn vị pháp lý; văn bản dài nhưng không có cấu trúc sẽ
fallback sang cửa sổ overlap 2.000/200, đúng chiến lược C2.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from collections.abc import Iterable

from src.services.retrieval.common import RetrievedChunk

DATASET_URL = "https://huggingface.co/datasets/YuITC/Vietnamese-Legal-Documents"
SOURCE_TYPE = "huggingface_dataset"
CHUNKING_METHOD = "legal_hybrid"
DEFAULT_MAX_CHARS = 4000
DEFAULT_FALLBACK_MAX_CHARS = 2000
DEFAULT_OVERLAP_CHARS = 200

_LINE_PREFIX = r"^[\s#>*_+\-]*"
CHAPTER_RE = re.compile(
    _LINE_PREFIX + r"(Ch(?:ươ|uo)ng\s+[IVXLCDM\d]+)\b", re.I | re.M
)
SECTION_RE = re.compile(_LINE_PREFIX + r"(M(?:ụ|u)c\s+\d+)\b", re.I | re.M)
ARTICLE_RE = re.compile(_LINE_PREFIX + r"(Điều\s+\d+[a-zA-Z]?)\b", re.I | re.M)
CLAUSE_RE = re.compile(
    _LINE_PREFIX + r"(?:Kho(?:ả|a)n\s+)?(\d+)[\.)]\s+", re.I | re.M
)
POINT_RE = re.compile(
    _LINE_PREFIX + r"(?:Đi(?:ể|e)m\s+)?([a-zđ])[\.)]\s+", re.I | re.M
)


@dataclass
class _Path:
    chapter: str = ""
    section: str = ""
    article: str = ""
    clause: str = ""
    point: str = ""

    def copy(self) -> _Path:
        return _Path(**self.__dict__)


@dataclass
class _Unit:
    content: str
    path: _Path
    chunk_type: str = "legal_unit"
    flags: list[str] = field(default_factory=list)
    extra: dict[str, object] = field(default_factory=dict)


def chunks_from_legal_record(
    record_id: str | int,
    text: str,
    *,
    dataset_id: str = "YuITC/Vietnamese-Legal-Documents",
    dataset_revision: str = "main",
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    fallback_max_chars: int = DEFAULT_FALLBACK_MAX_CHARS,
) -> list[RetrievedChunk]:
    """Cắt một văn bản theo cùng thứ tự ưu tiên như C2 ``legal_hybrid``.

    ``max_chars`` là ngưỡng tách đơn vị cấu trúc (4.000 ở C2); overlap chỉ áp
    dụng khi text dài nhưng parser không lấy được Điều/Khoản/Điểm hữu ích.
    """
    if max_chars <= 0 or fallback_max_chars <= 0:
        raise ValueError("max_chars phải lớn hơn 0")
    if overlap_chars < 0 or overlap_chars >= fallback_max_chars:
        raise ValueError("overlap_chars phải nhỏ hơn fallback_max_chars")
    normalized = _normalize(text)
    if not normalized:
        return []
    source_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    units = _extract_units(normalized)
    has_structure = any(unit.path.article or unit.path.clause or unit.path.point for unit in units)

    if not has_structure and any(len(unit.content) > fallback_max_chars for unit in units):
        units = _overlap_fallback(normalized, fallback_max_chars, overlap_chars)
    else:
        units = list(_split_structured_units(units, max_chars))

    record_key = str(record_id)
    return [
        _to_chunk(
            record_key=record_key,
            index=index,
            unit=unit,
            source_hash=source_hash,
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
        )
        for index, unit in enumerate(units)
        if unit.content.strip()
    ]


def _normalize(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_units(text: str) -> list[_Unit]:
    articles = list(ARTICLE_RE.finditer(text))
    if not articles:
        return [
            _Unit(
                content=text,
                path=_Path(),
                chunk_type="unstructured_body",
                flags=["ambiguous_structure", "incomplete_structure"],
            )
        ]
    headings = sorted(
        [
            *( (match.start(), "chapter", match.group(1)) for match in CHAPTER_RE.finditer(text)),
            *( (match.start(), "section", match.group(1)) for match in SECTION_RE.finditer(text)),
        ]
    )
    units: list[_Unit] = []
    preamble = text[: articles[0].start()].strip()
    if preamble:
        units.append(_Unit(preamble, _Path(), chunk_type="front_matter"))
    for index, article in enumerate(articles):
        end = articles[index + 1].start() if index + 1 < len(articles) else len(text)
        path = _path_at(headings, article.start())
        path.article = article.group(1)
        units.extend(_article_units(text[article.start() : end].strip(), path))
    return units


def _path_at(headings: list[tuple[int, str, str]], position: int) -> _Path:
    path = _Path()
    for start, kind, label in headings:
        if start > position:
            break
        if kind == "chapter":
            path.chapter, path.section = label, ""
        else:
            path.section = label
    return path


def _article_units(text: str, path: _Path) -> list[_Unit]:
    clauses = [match for match in CLAUSE_RE.finditer(text) if _is_line_start(text, match.start())]
    if not clauses:
        return [_Unit(text, path.copy(), extra=_point_metadata(text))]
    intro = text[: clauses[0].start()].rstrip()
    units: list[_Unit] = []
    for index, clause in enumerate(clauses):
        end = clauses[index + 1].start() if index + 1 < len(clauses) else len(text)
        clause_path = path.copy()
        clause_path.clause = f"Khoản {clause.group(1)}"
        extra = _point_metadata(text[clause.start() : end])
        if intro:
            extra["article_heading"] = intro
        units.append(_Unit(text[clause.start() : end].strip(), clause_path, extra=extra))
    return units


def _split_structured_units(units: list[_Unit], max_chars: int) -> Iterable[_Unit]:
    for unit in units:
        if len(unit.content) <= max_chars:
            yield unit
            continue
        children = _split_oversized_unit(unit, max_chars)
        parent = _stable_id("chunk_parent", _path_key(unit.path), unit.content)
        for child_index, child in enumerate(children):
            child.extra.update(
                {"parent_chunk_id": parent, "child_index": child_index, "child_count": len(children)}
            )
            child.flags = [*child.flags, "oversized_split"]
            yield child


def _split_oversized_unit(unit: _Unit, max_chars: int) -> list[_Unit]:
    points = [match for match in POINT_RE.finditer(unit.content) if _is_line_start(unit.content, match.start())]
    candidates: list[_Unit] = []
    if points and unit.path.article and unit.path.clause:
        intro = unit.content[: points[0].start()].rstrip()
        for index, point in enumerate(points):
            end = points[index + 1].start() if index + 1 < len(points) else len(unit.content)
            path = unit.path.copy()
            path.point = f"Điểm {point.group(1)}"
            extra = dict(unit.extra)
            if intro:
                extra["parent_intro"] = intro
            candidates.append(_Unit(unit.content[point.start() : end].strip(), path, unit.chunk_type, list(unit.flags), extra))
    else:
        candidates = [_Unit(part, unit.path.copy(), unit.chunk_type, list(unit.flags), dict(unit.extra)) for part in _cascade_split(unit.content, max_chars)]
    bounded: list[_Unit] = []
    for candidate in candidates:
        for part in _cascade_split(candidate.content, max_chars):
            bounded.append(_Unit(part, candidate.path.copy(), candidate.chunk_type, list(candidate.flags), dict(candidate.extra)))
    return bounded


def _cascade_split(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    for separator in ("\n\n", "\n"):
        pieces = text.split(separator)
        if len(pieces) == 1:
            continue
        packed: list[str] = []
        current = ""
        for piece in pieces:
            candidate = piece if not current else current + separator + piece
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    packed.append(current)
                current = piece
        if current:
            packed.append(current)
        if all(len(part) <= max_chars for part in packed):
            return packed
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _overlap_fallback(text: str, max_chars: int, overlap_chars: int) -> list[_Unit]:
    units: list[_Unit] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        units.append(
            _Unit(
                text[start:end].strip(),
                _Path(),
                chunk_type="overlap_fallback",
                flags=["ambiguous_structure", "incomplete_structure"],
                extra={"fallback_strategy": "overlap", "char_start": start, "char_end": end},
            )
        )
        if end == len(text):
            break
        start = end - overlap_chars
    return units


def _to_chunk(
    *, record_key: str, index: int, unit: _Unit, source_hash: str,
    dataset_id: str, dataset_revision: str,
) -> RetrievedChunk:
    path = unit.path
    chunk_id = _stable_id("chunk", CHUNKING_METHOD, record_key, str(index), _path_key(path), unit.content)
    metadata: dict[str, object] = {
        "chunk_id": chunk_id,
        "procedure_id": f"legal:{record_key}",
        "procedure_name": f"Văn bản pháp luật #{record_key}",
        "section": path.article or path.section or "văn_bản_pháp_luật",
        "source_type": SOURCE_TYPE,
        "dataset_id": dataset_id,
        "dataset_revision": dataset_revision,
        "legal_record_id": record_key,
        "source_hash": source_hash,
        "source_url": DATASET_URL,
        "chunking_method": CHUNKING_METHOD,
        "chunk_type": unit.chunk_type,
        "chapter": path.chapter,
        "article": path.article,
        "clause": path.clause,
        "point": path.point,
        "parse_flags": ",".join(unit.flags),
        "content_hash": hashlib.sha256(unit.content.encode("utf-8")).hexdigest()[:16],
        **unit.extra,
    }
    return RetrievedChunk(content=unit.content, metadata=metadata)


def _point_metadata(content: str) -> dict[str, object]:
    points = [f"Điểm {match.group(1)}" for match in POINT_RE.finditer(content) if _is_line_start(content, match.start())]
    return {"points": ",".join(points)} if points else {}


def _is_line_start(text: str, position: int) -> bool:
    return position == 0 or text[position - 1] == "\n"


def _path_key(path: _Path) -> str:
    return "|".join([path.chapter, path.section, path.article, path.clause, path.point])


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"
