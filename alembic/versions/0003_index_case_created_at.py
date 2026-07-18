"""Add index to support ApplicationRepository.list's created_at ordering."""

from alembic import op
import sqlalchemy as sa


revision = "0003_index_case_created_at"
down_revision = "0002_add_application_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("application_cases")}
    if "ix_application_cases_org_created_at" not in indexes:
        op.create_index(
            "ix_application_cases_org_created_at",
            "application_cases",
            ["organization_id", "created_at"],
        )


def downgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("application_cases")}
    if "ix_application_cases_org_created_at" in indexes:
        op.drop_index("ix_application_cases_org_created_at", table_name="application_cases")
