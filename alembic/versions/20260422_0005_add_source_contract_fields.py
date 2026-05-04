"""Add source contract fields

Revision ID: 20260422_0005
Revises: 20260415_0004
Create Date: 2026-04-22 19:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260422_0005"
down_revision = "20260415_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.add_column(sa.Column("source_contract_number", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("source_contract_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.drop_column("source_contract_date")
        batch_op.drop_column("source_contract_number")
