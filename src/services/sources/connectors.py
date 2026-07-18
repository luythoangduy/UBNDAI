"""Connectors discover procedures from allow-listed portal index pages."""

from __future__ import annotations

import asyncio
import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, UTC
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from src.models import ProcedureDocument, ProcedureSection

SECTION_ALIASES = {
    "thanh phan ho so": "thanh_phan_ho_so",
    "cach thuc thuc hien": "cach_thuc_thuc_hien",
    "trinh tu thuc hien": "cach_thuc_thuc_hien",
    "thoi han giai quyet": "thoi_han",
    "thoi han": "thoi_han",
    "phi le phi": "phi_le_phi",
    "le phi": "phi_le_phi",
    "yeu cau dieu kien": "dieu_kien",
    "dieu kien": "dieu_kien",
    "can cu phap ly": "can_cu_phap_ly",
    "bieu mau": "bieu_mau",
    "mau don": "bieu_mau",
}


@dataclass(frozen=True)
class RawDocument:
    url: str
    content_type: str
    body: bytes
    retrieved_at: datetime
    checksum: str


class ProcedureConnector(ABC):
    @abstractmethod
    async def discover(self) -> list[str]: ...

    @abstractmethod
    async def fetch(self, url: str) -> RawDocument: ...

    @abstractmethod
    async def extract(self, document: RawDocument) -> ProcedureDocument: ...


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


class _SectionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._heading_depth = 0
        self._current = "tong_quan"
        self._parts: dict[str, list[str]] = {"tong_quan": []}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        folded = tag.casefold()
        if folded == "title":
            self._in_title = True
        if folded in {"h1", "h2", "h3", "h4", "strong"}:
            self._heading_depth += 1
        if folded in {"p", "div", "li", "br", "tr"}:
            self._parts.setdefault(self._current, []).append("\n")

    def handle_endtag(self, tag: str) -> None:
        folded = tag.casefold()
        if folded == "title":
            self._in_title = False
        if folded in {"h1", "h2", "h3", "h4", "strong"}:
            self._heading_depth = max(0, self._heading_depth - 1)

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        normalized = _fold(text)
        if self._heading_depth:
            section = next(
                (value for label, value in SECTION_ALIASES.items() if label in normalized),
                None,
            )
            if section:
                self._current = section
                self._parts.setdefault(section, [])
                return
        self._parts.setdefault(self._current, []).append(text)

    def sections(self) -> dict[str, str]:
        return {
            key: re.sub(r"\s*\n\s*", "\n", " ".join(parts)).strip()
            for key, parts in self._parts.items()
            if " ".join(parts).strip()
        }


class DvcNationalConnector(ProcedureConnector):
    """Crawler for official DVC pages; procedure URLs are never enumerated in code."""

    def __init__(
        self,
        index_urls: list[str],
        *,
        allowed_domains: set[str] | None = None,
        rate_limit_seconds: float = 0.5,
        timeout_seconds: float = 30,
        max_document_bytes: int = 20 * 1024 * 1024,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.index_urls = index_urls
        self.allowed_domains = allowed_domains or {"dichvucong.gov.vn", "thutuc.dichvucong.gov.vn"}
        self.rate_limit_seconds = max(0, rate_limit_seconds)
        self.timeout_seconds = timeout_seconds
        self.max_document_bytes = max_document_bytes
        self._client = client

    async def discover(self) -> list[str]:
        found: set[str] = set()
        for index_url in self.index_urls:
            self._validate_url(index_url)
            raw = await self.fetch(index_url)
            if "html" not in raw.content_type:
                continue
            parser = _LinkParser()
            parser.feed(raw.body.decode("utf-8", errors="replace"))
            for href in parser.links:
                candidate = urljoin(index_url, href)
                if self._is_procedure_detail(candidate):
                    found.add(candidate)
        return sorted(found)

    async def fetch(self, url: str) -> RawDocument:
        self._validate_url(url)
        if self.rate_limit_seconds:
            await asyncio.sleep(self.rate_limit_seconds)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "TTHC-Assist/0.1 official-source-sync"},
        )
        try:
            current_url = url
            for _ in range(6):
                response = await client.get(current_url, follow_redirects=False)
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect thiếu Location")
                    current_url = urljoin(current_url, location)
                    self._validate_url(current_url)
                    continue
                response.raise_for_status()
                self._validate_url(str(response.url))
                body = response.content
                if len(body) > self.max_document_bytes:
                    raise ValueError("Nguồn vượt giới hạn kích thước cho phép")
                return RawDocument(
                    url=str(response.url),
                    content_type=response.headers.get("content-type", "application/octet-stream").split(";", 1)[0],
                    body=body,
                    retrieved_at=datetime.now(UTC),
                    checksum=f"sha256:{hashlib.sha256(body).hexdigest()}",
                )
            raise ValueError("Nguồn redirect quá nhiều lần")
        finally:
            if owns_client:
                await client.aclose()

    async def extract(self, document: RawDocument) -> ProcedureDocument:
        if "html" not in document.content_type:
            raise ValueError(f"Chưa có bộ tách an toàn cho {document.content_type}")
        parser = _SectionParser()
        parser.feed(document.body.decode("utf-8", errors="replace"))
        query = parse_qs(urlparse(document.url).query)
        procedure_id = next(
            (query[key][0] for key in ("ma_thu_tuc", "procedure_id", "id") if query.get(key)),
            hashlib.sha256(document.url.encode()).hexdigest()[:16],
        )
        name = parser.title or f"Thủ tục {procedure_id}"
        now = document.retrieved_at
        sections = [
            ProcedureSection(
                procedure_id=procedure_id,
                procedure_name=name,
                section=section,  # type: ignore[arg-type]
                content=content,
                source_url=document.url,
                retrieved_at=now,
                source_hash=document.checksum,
            )
            for section, content in parser.sections().items()
        ]
        return ProcedureDocument(
            procedure_id=procedure_id,
            procedure_name=name,
            source_url=document.url,
            retrieved_at=now,
            source_hash=document.checksum,
            sections=sections,
        )

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or host not in self.allowed_domains:
            raise ValueError(f"Nguồn không nằm trong allow-list: {url}")

    def _is_procedure_detail(self, url: str) -> bool:
        try:
            self._validate_url(url)
        except ValueError:
            return False
        folded = url.casefold()
        return "chi-tiet" in folded or "ma_thu_tuc=" in folded or "procedure_id=" in folded


def _fold(value: str) -> str:
    from src.services.retrieval.common import fold_ascii

    return fold_ascii(value)
