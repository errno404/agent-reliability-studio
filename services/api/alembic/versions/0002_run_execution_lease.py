"""run_executions lease columns (fencing token + expiry)

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("run_executions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lease_token", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_exec_lease", ["status", "lease_expires_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("run_executions", schema=None) as batch_op:
        batch_op.drop_index("ix_exec_lease")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("lease_token")
