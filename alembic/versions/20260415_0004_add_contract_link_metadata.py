"""Add contract link metadata fields

Revision ID: 20260415_0004
Revises: 20260414_0003
Create Date: 2026-04-15 11:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260415_0004"
down_revision = "20260414_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.add_column(sa.Column("contract_link_status", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("contract_link_strategy", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("contract_link_reason", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("contract_link_score", sa.Integer(), nullable=True))
        batch_op.create_index("ix_waste_objects_contract_link_status", ["contract_link_status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.drop_index("ix_waste_objects_contract_link_status")
        batch_op.drop_column("contract_link_score")
        batch_op.drop_column("contract_link_reason")
        batch_op.drop_column("contract_link_strategy")
        batch_op.drop_column("contract_link_status")
