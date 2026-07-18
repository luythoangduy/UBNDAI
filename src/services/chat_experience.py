"""Build capability-driven chat actions, official template provenance and source trace."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from src.config import settings
from src.models import (
    ChatAction,
    ChatCacheInfo,
    ChatStarterResponse,
    ChatTemplateResource,
    EvidenceStep,
    TemplateCitation,
)
from src.services import catalog
from src.services.drafts import registry as draft_registry
from src.services.procedure_capabilities import capabilities_for
from src.services.response_cache import get_json, set_json
from src.services.retrieval.raw_procedures import get_document as get_raw_document

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatExperience:
    procedure_id: str | None
    actions: list[ChatAction]
    templates: list[ChatTemplateResource]
    evidence: list[EvidenceStep]
    cache: ChatCacheInfo


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            text = " ".join(data.split())
            if text:
                self._text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


async def starter_experience() -> ChatStarterResponse:
    procedures = [
        item
        for item in catalog.load_catalog().values()
        if item.status in {"approved", "published"}
    ]
    actions = [
        ChatAction(
            id=f"discover-{item.id}",
            label=item.name,
            description=f"{item.agency}" + (f" · Mã {item.national_code}" if item.national_code else ""),
            kind="send_message",
            value=f"Tôi muốn làm thủ tục {item.name}",
            icon="search",
            primary=index == 0,
        )
        for index, item in enumerate(procedures[:4])
    ]
    catalog_fingerprint = hashlib.sha256(
        "|".join(f"{item.id}:{item.status}:{item.source_hash or item.source_url}" for item in procedures).encode()
    ).hexdigest()[:16]
    starter_key = f"chat-experience:starter:v2:{catalog_fingerprint}"
    cache_result = await get_json(starter_key)
    backend = cache_result.backend
    if not cache_result.hit:
        backend = await set_json(
            starter_key,
            {"procedure_ids": [item.id for item in procedures]},
            ttl_seconds=settings.chat_experience_cache_ttl_s,
        )
    cache = _cache_info(backend, cache_result.hit)
    return ChatStarterResponse(
        reply=(
            "Bạn có thể hỏi bất kỳ thủ tục hành chính nào. Mình sẽ tra cứu nguồn đã "
            "đồng bộ và nguồn Chính phủ; workflow có dữ liệu kiểm duyệt sẽ có thêm "
            "checklist hoặc biểu mẫu để thực hiện ngay."
        ),
        actions=actions,
        evidence=[
            EvidenceStep(
                id="hybrid-search",
                label="Tìm thủ tục",
                detail="Đối chiếu tên gọi và nội dung thủ tục trong danh mục",
                status="ready",
            ),
            EvidenceStep(
                id="official-first",
                label="Nguồn ưu tiên",
                detail="Cổng DVC, Cổng TTĐT Chính phủ và Bộ/ngành",
                status="ready",
                source_url=settings.dvc_search_url,
            ),
        ],
        cache=cache,
    )


async def build_experience(procedure_id: str | None, query: str) -> ChatExperience:
    if not procedure_id:
        return await _search_experience(query)
    procedure = catalog.get_procedure(procedure_id)
    raw = get_raw_document(procedure_id) if procedure is None else None
    if procedure is None and raw is None:
        return await _search_experience(query)
    source_url = procedure.source_url if procedure else raw.source_url
    source_hash = (
        procedure.source_hash
        or hashlib.sha256(procedure.model_dump_json().encode()).hexdigest()
        if procedure
        else raw.source_hash
    )
    registered_templates = draft_registry.list_templates(procedure_id)
    template_version = ",".join(
        f"{item.id}:{item.version}:{item.source_checked_on}"
        for item in registered_templates
    ) or "none"
    fingerprint = hashlib.sha256(f"{source_hash}:{template_version}".encode()).hexdigest()[:20]
    key = f"chat-experience:procedure:v2:{procedure_id}:{fingerprint}"
    cached = await get_json(key)
    if cached.value is not None:
        return ChatExperience(
            procedure_id=procedure_id,
            actions=[ChatAction.model_validate(item) for item in cached.value["actions"]],
            templates=[ChatTemplateResource.model_validate(item) for item in cached.value["templates"]],
            evidence=[
                EvidenceStep(
                    id="cache",
                    label="Cache nguồn",
                    detail="Đã dùng kết quả có cùng checksum nguồn",
                    status="cache_hit",
                ),
                *[EvidenceStep.model_validate(item) for item in cached.value["evidence"]],
            ],
            cache=_cache_info(cached.backend, True),
        )

    templates = _registry_templates(procedure_id)
    remote_templates: list[ChatTemplateResource] = []
    evidence = [
        EvidenceStep(
            id="hybrid-search",
            label="Tìm thủ tục",
            detail="Đã xác định đúng thủ tục và đối chiếu nội dung liên quan",
            status="ready",
        )
    ]
    if source_url:
        if is_official_url(source_url):
            evidence.append(
                EvidenceStep(
                    id="official-source",
                    label="Nguồn thủ tục",
                    detail=f"Nguồn Chính phủ · {urlparse(source_url).hostname}",
                    status="ready",
                    source_url=source_url,
                )
            )
        else:
            evidence.append(
                EvidenceStep(
                    id="official-source",
                    label="Nguồn thủ tục",
                    detail="Nguồn chưa thuộc danh sách Chính phủ ưu tiên",
                    status="fallback",
                    source_url=source_url,
                )
            )
        discovered, fetch_step = await _fetch_official_page(source_url, procedure_id)
        remote_templates.extend(discovered)
        evidence.append(fetch_step)
    templates = _deduplicate_templates([*templates, *remote_templates])
    actions = _actions(procedure_id, source_url, procedure, templates)
    payload = {
        "actions": [item.model_dump(mode="json") for item in actions],
        "templates": [item.model_dump(mode="json") for item in templates],
        "evidence": [item.model_dump(mode="json") for item in evidence],
    }
    backend = await set_json(
        key, payload, ttl_seconds=settings.chat_experience_cache_ttl_s
    )
    return ChatExperience(
        procedure_id=procedure_id,
        actions=actions,
        templates=templates,
        evidence=evidence,
        cache=_cache_info(backend, False),
    )


def _registry_templates(procedure_id: str) -> list[ChatTemplateResource]:
    resources: list[ChatTemplateResource] = []
    for template in draft_registry.list_templates(procedure_id):
        citations = sorted(
            [
                TemplateCitation(
                    document_number=source.document_number,
                    title=source.title,
                    issuing_authority=source.issuing_authority,
                    role=source.role,
                    source_url=str(source.source_url),
                    official=is_official_url(str(source.source_url)),
                    priority=_source_priority(str(source.source_url), source.role),
                )
                for source in template.legal_sources
            ],
            key=lambda item: item.priority,
            reverse=True,
        )
        primary = citations[0]
        resources.append(
            ChatTemplateResource(
                template_id=template.id,
                title=template.output_name,
                version=template.version,
                source_checked_on=template.source_checked_on.isoformat(),
                field_count=len(template.fields),
                source_url=primary.source_url,
                source_label=f"{primary.document_number} · {primary.issuing_authority}",
                official_source=primary.official,
                citations=citations,
            )
        )
    return resources


def _actions(
    procedure_id: str,
    source_url: str | None,
    procedure: object | None,
    templates: list[ChatTemplateResource],
) -> list[ChatAction]:
    actions: list[ChatAction] = []
    caps = capabilities_for(procedure_id)
    if caps.checklist:
        actions.append(ChatAction(id="checklist", label="Hồ sơ cần gì?", description="Tạo checklist theo trường hợp", kind="send_message", value="Hồ sơ cần chuẩn bị những gì?", icon="checklist", primary=True))
    actions.append(ChatAction(id="time-fee", label="Phí & thời hạn", description="Đối chiếu trực tiếp từ nguồn", kind="send_message", value="Lệ phí và thời hạn giải quyết là bao lâu?", icon="clock"))
    if templates:
        actions.append(ChatAction(id="templates", label="Lấy biểu mẫu", description=f"{len(templates)} mẫu có provenance", kind="send_message", value="Cho tôi xem các biểu mẫu và nguồn ban hành", icon="template"))
    if caps.dynamic_form:
        actions.append(ChatAction(id="start-form", label="Bắt đầu điền", description="Mở biểu mẫu động, có OCR hỗ trợ", kind="start_form", value=procedure_id, icon="form", primary=True))
    if source_url:
        actions.append(ChatAction(id="official-source", label="Mở nguồn gốc", description=urlparse(source_url).hostname or "Nguồn thủ tục", kind="open_url", value=source_url, icon="source"))
    return actions


async def _search_experience(query: str) -> ChatExperience:
    query_key = hashlib.sha256(query.casefold().strip().encode()).hexdigest()[:20]
    key = f"chat-experience:official-search:v1:{query_key}"
    cached = await get_json(key)
    if cached.value is not None:
        return ChatExperience(
            procedure_id=None,
            actions=[ChatAction.model_validate(item) for item in cached.value["actions"]],
            templates=[],
            evidence=[EvidenceStep.model_validate(item) for item in cached.value["evidence"]],
            cache=_cache_info(cached.backend, True),
        )
    actions: list[ChatAction] = []
    status = "unavailable"
    detail = "Cổng DVC chưa phản hồi; tiếp tục dùng catalog/RAG đã cache"
    if settings.official_source_live_fetch and query.strip():
        search_url = f"{settings.dvc_search_url}?keyword={quote_plus(query.strip())}"
        try:
            async with httpx.AsyncClient(timeout=settings.official_source_timeout_s, follow_redirects=False) as client:
                response = await client.get(search_url, headers={"User-Agent": "TTHC-Assist/0.1 official-search"})
                response.raise_for_status()
            parser = _LinkCollector()
            parser.feed(response.text)
            seen: set[str] = set()
            for href, label in parser.links:
                url = urljoin(search_url, href)
                if url in seen or not is_official_url(url) or not _is_procedure_url(url):
                    continue
                seen.add(url)
                actions.append(ChatAction(id=f"search-{len(actions)}", label=label or "Xem thủ tục phù hợp", description=urlparse(url).hostname or "Nguồn Chính phủ", kind="open_url", value=url, icon="search"))
                if len(actions) == 4:
                    break
            status = "ready"
            detail = f"Đã tìm Cổng DVC Quốc gia · {len(actions)} kết quả"
        except Exception:
            logger.info("Official DVC search unavailable", exc_info=True)
    evidence = [EvidenceStep(id="official-search", label="Tìm nguồn Chính phủ", detail=detail, status=status, source_url=settings.dvc_search_url)]
    payload = {"actions": [item.model_dump(mode="json") for item in actions], "evidence": [item.model_dump(mode="json") for item in evidence]}
    backend = await set_json(key, payload, ttl_seconds=min(settings.chat_experience_cache_ttl_s, 600))
    return ChatExperience(None, actions, [], evidence, _cache_info(backend, False))


async def _fetch_official_page(
    source_url: str, procedure_id: str
) -> tuple[list[ChatTemplateResource], EvidenceStep]:
    if not settings.official_source_live_fetch or not is_official_url(source_url):
        return [], EvidenceStep(id="official-api", label="Kéo nguồn trực tiếp", detail="Đang dùng snapshot đã kiểm duyệt", status="fallback", source_url=source_url)
    try:
        async with httpx.AsyncClient(timeout=settings.official_source_timeout_s, follow_redirects=False) as client:
            response = await client.get(source_url, headers={"User-Agent": "TTHC-Assist/0.1 official-source"})
            response.raise_for_status()
        parser = _LinkCollector()
        parser.feed(response.text)
        resources: list[ChatTemplateResource] = []
        for href, label in parser.links:
            url = urljoin(source_url, href)
            if not is_official_url(url) or not _looks_like_template(url, label):
                continue
            title = label or url.rsplit("/", 1)[-1]
            digest = hashlib.sha256(url.encode()).hexdigest()[:12]
            citation = TemplateCitation(document_number="Nguồn Cổng DVC", title=title, issuing_authority="Cơ quan công bố TTHC", role="output_template", source_url=url, official=True, priority=1100)
            resources.append(ChatTemplateResource(template_id=f"remote.{procedure_id}.{digest}", title=title, version="official-live", source_checked_on="live", field_count=0, source_url=url, source_label="Tệp từ nguồn thủ tục chính thức", official_source=True, citations=[citation]))
            if len(resources) == 6:
                break
        return resources, EvidenceStep(id="official-api", label="Kéo nguồn trực tiếp", detail=f"Đã kiểm tra trang gốc · {len(resources)} tệp biểu mẫu", status="ready", source_url=source_url)
    except Exception:
        logger.info("Official source fetch unavailable for %s", source_url, exc_info=True)
        return [], EvidenceStep(id="official-api", label="Kéo nguồn trực tiếp", detail="Nguồn live chưa phản hồi; dùng snapshot có checksum", status="fallback", source_url=source_url)


def is_official_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return bool(
        host.endswith(".gov.vn")
        or host in {"dichvucong.gov.vn", "thutuc.dichvucong.gov.vn", "vanban.chinhphu.vn", "vbpl.vn"}
        or host.endswith(".moj.gov.vn")
    )


def _source_priority(url: str, role: str) -> int:
    role_score = 1000 if role == "output_template" else 100 if role == "consolidated_reference" else 50
    if is_official_url(url):
        return role_score + 100
    return role_score


def _is_procedure_url(url: str) -> bool:
    folded = url.casefold()
    return "chi-tiet" in folded or "ma_thu_tuc=" in folded


def _looks_like_template(url: str, label: str) -> bool:
    folded = f"{url} {label}".casefold()
    return any(token in folded for token in ("mẫu", "mau", ".doc", ".docx", ".pdf", ".xls", ".xlsx", ".rar"))


def _deduplicate_templates(items: list[ChatTemplateResource]) -> list[ChatTemplateResource]:
    seen: set[str] = set()
    result: list[ChatTemplateResource] = []
    for item in items:
        key = item.source_url.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _cache_info(backend: str, hit: bool) -> ChatCacheInfo:
    normalized = backend if backend in {"redis", "memory"} else "none"
    return ChatCacheInfo(
        backend=normalized,
        status="hit" if hit else "miss",
        ttl_seconds=settings.chat_experience_cache_ttl_s,
    )
