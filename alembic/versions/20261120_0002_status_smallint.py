"""payment.status: enum -> smallint (0=PENDING, 1=SUCCEEDED, 2=FAILED); outbox.attempts

Revision ID: 0002_status_smallint
Revises: 0001_initial
Create Date: 2026-11-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_status_smallint"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the default first: it references the enum type and would block DROP TYPE
    op.execute("ALTER TABLE payments ALTER COLUMN status DROP DEFAULT")
    op.execute("""
        ALTER TABLE payments
        ALTER COLUMN status TYPE smallint
        USING CASE status
            WHEN 'PENDING' THEN 0
            WHEN 'SUCCEEDED' THEN 1
            WHEN 'FAILED' THEN 2
        END
    """)
    op.execute("ALTER TABLE payments ALTER COLUMN status SET DEFAULT 0")
    op.execute("DROP TYPE IF EXISTS payment_status")

    op.add_column(
        "outbox",
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("outbox", "attempts")

    op.execute("CREATE TYPE payment_status AS ENUM ('PENDING', 'SUCCEEDED', 'FAILED')")
    op.execute("ALTER TABLE payments ALTER COLUMN status DROP DEFAULT")
    op.execute("""
        ALTER TABLE payments
        ALTER COLUMN status TYPE payment_status
        USING CASE status
            WHEN 0 THEN 'PENDING'::payment_status
            WHEN 1 THEN 'SUCCEEDED'::payment_status
            WHEN 2 THEN 'FAILED'::payment_status
        END
    """)
    op.execute("ALTER TABLE payments ALTER COLUMN status SET DEFAULT 'PENDING'::payment_status")
