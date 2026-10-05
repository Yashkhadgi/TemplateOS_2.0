"""add_field_type_check

Revision ID: b9e5d2c8a740
Revises: 3f8d2c6a9e41
Create Date: 2026-09-06 12:00:00.000000

V1.3 Phase 3 — Member 3 (optional hardening): add a DB-level CHECK
constraint ck_template_field_type so the database — not just the ORM
@validates — rejects field types outside the MVP vocabulary
(text/textarea/date/number/list/signature).

batch_alter_table keeps this cross-dialect: SQLite recreates the table
(same pattern as 7c4e9a1b2d58); PostgreSQL uses a plain ALTER TABLE ...
ADD CONSTRAINT. Existing rows are guaranteed valid (every write path goes
through the ORM validator), so the constraint applies cleanly. The
downgrade drops it via batch as well.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b9e5d2c8a740"
down_revision = "3f8d2c6a9e41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("template_fields") as batch_op:
        batch_op.create_check_constraint(
            "ck_template_field_type",
            "field_type IN ('text','textarea','date','number','list','signature')",
        )


def downgrade() -> None:
    with op.batch_alter_table("template_fields") as batch_op:
        batch_op.drop_constraint("ck_template_field_type", type_="check")
