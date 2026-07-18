"""Persist guidance cases and chat transcripts on the configured database."""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_guidance_chat_persistence"
down_revision = "0003_index_case_created_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("cases"):
        op.create_table(
            "cases",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("data", sa.Text(), nullable=False),
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("case_messages"):
        op.create_table(
            "case_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("case_id", sa.String(64), nullable=False),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("response_json", sa.Text()),
            sa.ForeignKeyConstraint(
                ["case_id"], ["cases.id"], ondelete="CASCADE"
            ),
        )
    else:
        columns = {
            column["name"] for column in inspector.get_columns("case_messages")
        }
        if "response_json" not in columns:
            with op.batch_alter_table("case_messages") as batch:
                batch.add_column(sa.Column("response_json", sa.Text()))

    inspector = sa.inspect(op.get_bind())
    indexes = {
        index["name"] for index in inspector.get_indexes("case_messages")
    }
    if "ix_case_messages_case_id_id" not in indexes:
        op.create_index(
            "ix_case_messages_case_id_id",
            "case_messages",
            ["case_id", "id"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("case_messages"):
        op.drop_table("case_messages")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("cases"):
        op.drop_table("cases")
