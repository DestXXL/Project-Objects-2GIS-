"""Initial schema

Revision ID: 20260414_0001
Revises: 
Create Date: 2026-04-14 19:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260414_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inn", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("contact_person", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_legal_entities_inn"), "legal_entities", ["inn"], unique=True)

    op.create_table(
        "real_estates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("address_key", sa.String(length=500), nullable=False),
        sa.Column("district", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("street", sa.String(length=255), nullable=True),
        sa.Column("building", sa.String(length=255), nullable=True),
        sa.Column("cadastral_number", sa.String(length=255), nullable=True),
        sa.Column("area", sa.Float(), nullable=True),
        sa.Column("floors", sa.Integer(), nullable=True),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("object_type", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("address_key"),
    )
    op.create_index(op.f("ix_real_estates_address_key"), "real_estates", ["address_key"], unique=True)

    op.create_table(
        "waste_objects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("real_estate_id", sa.Integer(), nullable=False),
        sa.Column("legal_entity_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("waste_type", sa.String(length=255), nullable=True),
        sa.Column("waste_generation_norm", sa.String(length=255), nullable=True),
        sa.Column("calculation_unit", sa.String(length=100), nullable=True),
        sa.Column("calculation_value", sa.String(length=255), nullable=True),
        sa.Column("inn", sa.String(length=255), nullable=True),
        sa.Column("contract_number", sa.String(length=100), nullable=True),
        sa.Column("contract_date", sa.Date(), nullable=True),
        sa.Column("source_row_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["legal_entity_id"], ["legal_entities.id"]),
        sa.ForeignKeyConstraint(["real_estate_id"], ["real_estates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_waste_objects_category"), "waste_objects", ["category"], unique=False)
    op.create_index(op.f("ix_waste_objects_inn"), "waste_objects", ["inn"], unique=False)
    op.create_index(op.f("ix_waste_objects_legal_entity_id"), "waste_objects", ["legal_entity_id"], unique=False)
    op.create_index(op.f("ix_waste_objects_name"), "waste_objects", ["name"], unique=False)
    op.create_index(op.f("ix_waste_objects_real_estate_id"), "waste_objects", ["real_estate_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_waste_objects_real_estate_id"), table_name="waste_objects")
    op.drop_index(op.f("ix_waste_objects_name"), table_name="waste_objects")
    op.drop_index(op.f("ix_waste_objects_legal_entity_id"), table_name="waste_objects")
    op.drop_index(op.f("ix_waste_objects_inn"), table_name="waste_objects")
    op.drop_index(op.f("ix_waste_objects_category"), table_name="waste_objects")
    op.drop_table("waste_objects")
    op.drop_index(op.f("ix_real_estates_address_key"), table_name="real_estates")
    op.drop_table("real_estates")
    op.drop_index(op.f("ix_legal_entities_inn"), table_name="legal_entities")
    op.drop_table("legal_entities")
