"""Add billing method field

Revision ID: 20260414_0003
Revises: 20260414_0002
Create Date: 2026-04-14 22:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260414_0003"
down_revision = "20260414_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.add_column(sa.Column("billing_method", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("waste_objects") as batch_op:
        batch_op.drop_column("billing_method")
