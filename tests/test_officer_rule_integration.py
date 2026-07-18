from datetime import UTC, datetime

from src.models import ApplicationCase, CaseDocument, CaseSubmissionVersion
from src.services.officer_store import OfficerStore


def test_officer_rerun_validation_executes_catalog_rules():
    timestamp = datetime.now(UTC)
    runtime_store = OfficerStore(seed=False)
    case = ApplicationCase(
        id="case-ket-hon",
        case_code="CASE-KET-HON",
        organization_id="org-demo",
        citizen_id="citizen-demo",
        procedure_id="ket_hon",
        procedure_version_id="ket_hon-v1",
        status="in_officer_review",
        form_data={"_answers": {"khai_thac_duoc_cu_tru": True}},
        checklist={"to_khai_dang_ky_ket_hon": "missing"},
        created_at=timestamp,
        updated_at=timestamp,
    )
    submission = CaseSubmissionVersion(
        id="submission-ket-hon",
        case_id=case.id,
        version=1,
        form_data=case.form_data,
        checklist_snapshot=case.checklist,
        procedure_version_id=case.procedure_version_id,
        procedure_rule_version="ruleset-v1",
        created_at=timestamp,
        created_by=case.citizen_id,
    )
    runtime_store.cases[case.id] = case
    runtime_store.submissions[submission.id] = submission

    findings = runtime_store.rerun_validation(case.id, case.organization_id, "officer-demo")

    rule_findings = {finding.rule_id: finding for finding in findings if finding.type == "validation_rule"}
    assert {"KH-R1", "KH-R2", "KH-R3"} <= set(rule_findings)
    assert rule_findings["KH-R1"].severity == "error"
    assert rule_findings["KH-R1"].source == "rule"


def test_citizen_submission_runs_rule_precheck_automatically():
    timestamp = datetime.now(UTC)
    runtime_store = OfficerStore(seed=False)
    case = runtime_store.create_citizen_case("citizen-demo", "can_cuoc", "00001")
    case = runtime_store.update_citizen_case(
        case.id,
        case.citizen_id,
        case.version,
        {"nop_truc_tuyen": False, "co_thong_tin_csdl_dan_cu": True},
        {"ho_ten": "Nguyễn An"},
    )
    document = CaseDocument(
        id="document-can-cuoc",
        case_id=case.id,
        submission_version_id=f"draft:{case.id}",
        document_type="unknown",
        file_uri="private://document-can-cuoc",
        object_key="document-can-cuoc",
        original_filename="tai-lieu.png",
        content_type="image/png",
        size_bytes=100,
        sha256="a" * 64,
        ocr_status="ready",
        uploaded_at=timestamp,
    )
    runtime_store.documents[document.id] = document

    runtime_store.submit_citizen_case(
        case.id,
        case.citizen_id,
        case.version,
        "privacy-v1",
        "submit-can-cuoc",
    )

    findings = [
        finding
        for finding in runtime_store.findings.values()
        if finding.case_id == case.id and finding.type == "validation_rule"
    ]
    assert {finding.rule_id for finding in findings} == {"CC-R1", "CC-R2"}
    assert all(finding.severity == "error" for finding in findings)
