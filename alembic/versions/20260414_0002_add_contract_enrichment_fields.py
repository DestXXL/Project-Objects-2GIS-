"""Add contract enrichment fields

Revision ID: 20260414_0002
Revises: 20260414_0001
Create Date: 2026-04-14 21:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260414_0002"
down_revision = "20260414_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.add_column(sa.Column("contract_start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("comment", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.drop_column("comment")
        batch_op.drop_column("contract_start_date")
