"""expand_template_fields_metadata

Revision ID: 7c4e9a1b2d58
Revises: fb6604df0637
Create Date: 2026-08-28 21:40:00.000000

V1.3 Phase 1 — Member 3: expand template_fields to the full field-metadata
contract (field_label, section, example_value, validation_rule, ai_enabled)
plus the (template_id, field_name) unique constraint and a composite
(template_id, display_order) index. Additive only; existing rows survive.

Cross-dialect notes:
- ai_enabled is NOT NULL with server_default 'false' so existing rows backfill.
- The unique constraint is added via batch_alter_table so it also works on
  SQLite (tests), which cannot ALTER TABLE ... ADD CONSTRAINT natively.
- No timestamp defaults are touched here; see the fb6604df0637 patch for the
  CURRENT_TIMESTAMP fix.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c4e9a1b2d58"
down_revision = "fb6604df0637"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "template_fields",
        sa.Column("field_label", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "template_fields", sa.Column("section", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "template_fields",
        sa.Column("example_value", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "template_fields",
        sa.Column("validation_rule", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "template_fields",
        sa.Column(
            "ai_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )

    with op.batch_alter_table("template_fields") as batch_op:
        batch_op.create_unique_constraint(
            "uq_template_field_key", ["template_id", "field_name"]
        )

    op.create_index(
        "ix_template_fields_template_order",
        "template_fields",
        ["template_id", "display_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_template_fields_template_order", table_name="template_fields")

    with op.batch_alter_table("template_fields") as batch_op:
        batch_op.drop_constraint("uq_template_field_key", type_="unique")

    op.drop_column("template_fields", "ai_enabled")
    op.drop_column("template_fields", "validation_rule")
    op.drop_column("template_fields", "example_value")
    op.drop_column("template_fields", "section")
    op.drop_column("template_fields", "field_label")
