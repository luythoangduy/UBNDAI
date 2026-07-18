"""Add durable application review records and classification metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_application_management"
down_revision = "0001_persistence_baseline"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.engine.Inspector, table: str, column: str) -> bool:
    return any(item["name"] == column for item in inspector.get_columns(table))


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(table) and not _has_column(inspector, table, column.name):
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)


def _create_table_if_missing(name: str, *columns: sa.Column, **kwargs: object) -> None:
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns, **kwargs)


def _create_fk_if_missing(table: str, name: str, local: str, remote: str, ondelete: str) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item.get("name") for item in inspector.get_foreign_keys(table)}
    if name not in existing:
        remote_table, remote_column = remote.split(".", 1)
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(name, remote_table, [local], [remote_column], ondelete=ondelete)


def upgrade() -> None:
    for column in (
        sa.Column("classification_confidence", sa.Float()),
        sa.Column("classification_method", sa.String(64)),
        sa.Column("classification_evidence", sa.JSON(), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True)),
        sa.Column("analysis_started_at", sa.DateTime(timezone=True)),
        sa.Column("analysis_completed_at", sa.DateTime(timezone=True)),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
    ):
        _add_column_if_missing("application_cases", column)
    for column in (
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("template_code", sa.String(128)),
        sa.Column("template_version", sa.String(128)),
        sa.Column("extracted_text", sa.Text()),
    ):
        _add_column_if_missing("case_documents", column)

    for table, name, local, remote, ondelete in (
        ("case_submission_versions", "fk_submission_case", "case_id", "application_cases.id", "CASCADE"),
        ("case_documents", "fk_document_case", "case_id", "application_cases.id", "CASCADE"),
        ("case_documents", "fk_document_submission", "submission_version_id", "case_submission_versions.id", "SET NULL"),
        ("case_audit_events", "fk_audit_case", "case_id", "application_cases.id", "CASCADE"),
        ("routing_decisions", "fk_routing_case", "case_id", "application_cases.id", "CASCADE"),
        ("routing_decisions", "fk_routing_submission", "submission_version_id", "case_submission_versions.id", "CASCADE"),
        ("consent_records", "fk_consent_case", "case_id", "application_cases.id", "CASCADE"),
        ("consent_records", "fk_consent_submission", "submission_version_id", "case_submission_versions.id", "CASCADE"),
        ("notification_events", "fk_notification_case", "case_id", "application_cases.id", "SET NULL"),
    ):
        _create_fk_if_missing(table, name, local, remote, ondelete)

    _create_table_if_missing(
        "extracted_field_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("case_documents.id", name="fk_extracted_fields_document", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(128), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("bounding_box", sa.JSON()),
        sa.Column("review_status", sa.String(64), nullable=False, server_default="unreviewed"),
        sa.Column("previous_value", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_table_if_missing(
        "validation_findings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("application_cases.id", name="fk_validation_findings_case_id_application_cases", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_version_id", sa.String(64), sa.ForeignKey("case_submission_versions.id", name="fk_validation_findings_submission_version_id_case_submission_versions", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text()),
        sa.Column("rule_id", sa.String(128)),
        sa.Column("rule_version", sa.String(64)),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("field_keys", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_table_if_missing(
        "finding_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("finding_id", sa.String(64), sa.ForeignKey("validation_findings.id", name="fk_finding_decisions_finding", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("application_cases.id", name="fk_finding_decisions_case", ondelete="CASCADE"), nullable=False),
        sa.Column("officer_id", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_table_if_missing(
        "supplement_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("application_cases.id", name="fk_supplements_case", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_version_id", sa.String(64), sa.ForeignKey("case_submission_versions.id", name="fk_supplements_submission", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("public_message", sa.Text(), nullable=False),
        sa.Column("finding_ids", sa.JSON(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), nullable=False, server_default="sent"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_table_if_missing(
        "application_case_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), sa.ForeignKey("application_cases.id", name="fk_case_decisions_case", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_version_id", sa.String(64), sa.ForeignKey("case_submission_versions.id", name="fk_case_decisions_submission", ondelete="CASCADE"), nullable=False),
        sa.Column("officer_id", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("selected_finding_ids", sa.JSON(), nullable=False),
        sa.Column("citizen_message", sa.Text()),
        sa.Column("previous_status", sa.String(64), nullable=False),
        sa.Column("new_status", sa.String(64), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_decision_idempotency"),
    )

    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("application_cases")} if inspector.has_table("application_cases") else set()
    if "ix_application_cases_management_scope" not in indexes:
        op.create_index("ix_application_cases_management_scope", "application_cases", ["organization_id", "status", "submitted_at"])
    if "ix_application_cases_management_assignment" not in indexes:
        op.create_index("ix_application_cases_management_assignment", "application_cases", ["organization_id", "assigned_to", "status"])
    for table, name, columns in (
        ("extracted_field_records", "ix_extracted_field_records_document_id", ["document_id"]),
        ("validation_findings", "ix_validation_findings_current", ["case_id", "submission_version_id", "status", "severity"]),
        ("finding_decisions", "ix_finding_decisions_finding_id", ["finding_id"]),
        ("supplement_requests", "ix_supplement_requests_case_id", ["case_id"]),
        ("application_case_decisions", "ix_application_case_decisions_case_id", ["case_id"]),
    ):
        if sa.inspect(op.get_bind()).has_table(table):
            existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
            if name not in existing:
                op.create_index(name, table, columns)


def downgrade() -> None:
    for table in ("application_case_decisions", "supplement_requests", "finding_decisions", "validation_findings", "extracted_field_records"):
        if sa.inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
    for name, table in (
        ("ix_application_cases_management_assignment", "application_cases"),
        ("ix_application_cases_management_scope", "application_cases"),
    ):
        if name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}:
            op.drop_index(name, table_name=table)
    for table, name in (
        ("notification_events", "fk_notification_case"),
        ("consent_records", "fk_consent_submission"),
        ("consent_records", "fk_consent_case"),
        ("routing_decisions", "fk_routing_submission"),
        ("routing_decisions", "fk_routing_case"),
        ("case_audit_events", "fk_audit_case"),
        ("case_documents", "fk_document_submission"),
        ("case_documents", "fk_document_case"),
        ("case_submission_versions", "fk_submission_case"),
    ):
        existing = {item.get("name") for item in sa.inspect(op.get_bind()).get_foreign_keys(table)}
        if name in existing:
            with op.batch_alter_table(table) as batch:
                batch.drop_constraint(name, type_="foreignkey")
    for table, columns in (
        ("case_documents", ("extracted_text", "template_version", "template_code", "updated_at")),
        ("application_cases", ("returned_at", "processed_at", "processing_started_at", "analysis_completed_at", "analysis_started_at", "classified_at", "classification_evidence", "classification_method", "classification_confidence")),
    ):
        if sa.inspect(op.get_bind()).has_table(table):
            with op.batch_alter_table(table) as batch:
                for column in columns:
                    if _has_column(sa.inspect(op.get_bind()), table, column):
                        batch.drop_column(column)
