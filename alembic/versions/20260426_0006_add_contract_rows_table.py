"""Add contract rows table

Revision ID: 20260426_0006
Revises: 20260422_0005
Create Date: 2026-04-26 21:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260426_0006"
down_revision = "20260422_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_row_index", sa.Integer(), nullable=False),
        sa.Column("contract_number", sa.String(length=100), nullable=True),
        sa.Column("contract_date", sa.Date(), nullable=True),
        sa.Column("legal_entity_name", sa.String(length=255), nullable=True),
        sa.Column("waste_object_name", sa.String(length=255), nullable=True),
        sa.Column("inn", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("compact_address", sa.String(length=500), nullable=True),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("locality", sa.String(length=255), nullable=True),
        sa.Column("street", sa.String(length=255), nullable=True),
        sa.Column("building", sa.String(length=255), nullable=True),
        sa.Column("room", sa.String(length=255), nullable=True),
        sa.Column("material", sa.String(length=255), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("pickup_frequency", sa.String(length=255), nullable=True),
        sa.Column("contact_person", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("contract_start_date", sa.Date(), nullable=True),
        sa.Column("contract_link_status", sa.String(length=50), nullable=True),
        sa.Column("contract_link_strategy", sa.String(length=100), nullable=True),
        sa.Column("contract_link_reason", sa.String(length=500), nullable=True),
        sa.Column("linked_waste_object_id", sa.Integer(), nullable=True),
        sa.Column("link_mode", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["linked_waste_object_id"], ["waste_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contract_rows_source_row_index"), "contract_rows", ["source_row_index"], unique=False)
    op.create_index(op.f("ix_contract_rows_contract_number"), "contract_rows", ["contract_number"], unique=False)
    op.create_index(op.f("ix_contract_rows_waste_object_name"), "contract_rows", ["waste_object_name"], unique=False)
    op.create_index(op.f("ix_contract_rows_inn"), "contract_rows", ["inn"], unique=False)
    op.create_index(op.f("ix_contract_rows_address"), "contract_rows", ["address"], unique=False)
    op.create_index(op.f("ix_contract_rows_contract_link_status"), "contract_rows", ["contract_link_status"], unique=False)
    op.create_index(op.f("ix_contract_rows_linked_waste_object_id"), "contract_rows", ["linked_waste_object_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_contract_rows_linked_waste_object_id"), table_name="contract_rows")
    op.drop_index(op.f("ix_contract_rows_contract_link_status"), table_name="contract_rows")
    op.drop_index(op.f("ix_contract_rows_address"), table_name="contract_rows")
    op.drop_index(op.f("ix_contract_rows_inn"), table_name="contract_rows")
    op.drop_index(op.f("ix_contract_rows_waste_object_name"), table_name="contract_rows")
    op.drop_index(op.f("ix_contract_rows_contract_number"), table_name="contract_rows")
    op.drop_index(op.f("ix_contract_rows_source_row_index"), table_name="contract_rows")
    op.drop_table("contract_rows")
