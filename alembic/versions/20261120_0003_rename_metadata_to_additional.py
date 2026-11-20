"""rename payments.metadata -> payments.additional

Revision ID: 0003_rename_metadata
Revises: 0002_status_smallint
Create Date: 2026-11-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_rename_metadata"
down_revision: Union[str, None] = "0002_status_smallint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("payments", "metadata", new_column_name="additional")


def downgrade() -> None:
    op.alter_column("payments", "additional", new_column_name="metadata")
