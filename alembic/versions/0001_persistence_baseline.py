"""Create the original persistence foundation with explicit operations.

Revision ID: 0001_persistence_baseline

This revision intentionally does not call ``Base.metadata.create_all``.  A
revision must create only the schema it owns; otherwise importing later ORM
models would make a fresh 0001 database contain future tables before 0002.
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_persistence_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_cases",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_code", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("citizen_id", sa.String(128), nullable=False),
        sa.Column("procedure_id", sa.String(128), nullable=False),
        sa.Column("procedure_version_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="draft"),
        sa.Column("source_channel", sa.String(64), nullable=False, server_default="citizen_portal"),
        sa.Column("assigned_to", sa.String(128)),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
        sa.Column("current_submission_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("form_data", sa.JSON(), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_code", name="uq_application_cases_case_code"),
    )
    op.create_index("ix_application_cases_case_code", "application_cases", ["case_code"])
    op.create_index("ix_application_cases_organization_id", "application_cases", ["organization_id"])
    op.create_index("ix_application_cases_citizen_id", "application_cases", ["citizen_id"])
    op.create_index("ix_application_cases_status", "application_cases", ["status"])

    op.create_table(
        "case_submission_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("form_data", sa.JSON(), nullable=False),
        sa.Column("checklist_snapshot", sa.JSON(), nullable=False),
        sa.Column("procedure_version_id", sa.String(128), nullable=False),
        sa.Column("procedure_rule_version", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128)),
        sa.Column("source", sa.String(64), nullable=False, server_default="citizen_portal"),
        sa.UniqueConstraint("case_id", "version", name="uq_submission_case_version"),
    )
    op.create_index("ix_case_submission_versions_case_id", "case_submission_versions", ["case_id"])

    op.create_table(
        "case_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("submission_version_id", sa.String(64)),
        sa.Column("document_type", sa.String(128), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="upload_pending"),
        sa.Column("ocr_status", sa.String(64), nullable=False, server_default="pending"),
        sa.Column("ocr_engine", sa.String(128)),
        sa.Column("ocr_version", sa.String(128)),
        sa.Column("extracted_fields", sa.JSON(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("object_key", name="uq_case_documents_object_key"),
    )
    op.create_index("ix_case_documents_case_id", "case_documents", ["case_id"])
    op.create_index("ix_case_documents_submission_version_id", "case_documents", ["submission_version_id"])
    op.create_index("ix_case_documents_status", "case_documents", ["status"])

    op.create_table(
        "case_audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("object_type", sa.String(128), nullable=False),
        sa.Column("object_id", sa.String(128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_case_audit_events_case_id", "case_audit_events", ["case_id"])
    op.create_index("ix_case_audit_events_organization_id", "case_audit_events", ["organization_id"])

    op.create_table(
        "routing_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("submission_version_id", sa.String(64), nullable=False),
        sa.Column("procedure_id", sa.String(128), nullable=False),
        sa.Column("procedure_version_id", sa.String(128), nullable=False),
        sa.Column("locality_code", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("matched_rule", sa.String(256), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_routing_decisions_case_id", "routing_decisions", ["case_id"])
    op.create_index("ix_routing_decisions_organization_id", "routing_decisions", ["organization_id"])

    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("submission_version_id", sa.String(64), nullable=False),
        sa.Column("citizen_id", sa.String(128), nullable=False),
        sa.Column("consent_version", sa.String(64), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_hash", sa.String(128)),
    )
    op.create_index("ix_consent_records_case_id", "consent_records", ["case_id"])

    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_background_jobs_job_type", "background_jobs", ["job_type"])
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])

    op.create_table(
        "notification_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64)),
        sa.Column("recipient_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_notification_events_case_id", "notification_events", ["case_id"])
    op.create_index("ix_notification_events_recipient_id", "notification_events", ["recipient_id"])


def downgrade() -> None:
    for table in (
        "notification_events",
        "background_jobs",
        "consent_records",
        "routing_decisions",
        "case_audit_events",
        "case_documents",
        "case_submission_versions",
        "application_cases",
    ):
        op.drop_table(table)
