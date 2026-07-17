"""Create production persistence foundation.

Revision ID: 0001_persistence_baseline
"""
from alembic import op
from src.services.persistence import Base

revision = "0001_persistence_baseline"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
