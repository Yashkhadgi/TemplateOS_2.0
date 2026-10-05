"""add_template_fields_source

Revision ID: 3f8d2c6a9e41
Revises: 7c4e9a1b2d58
Create Date: 2026-08-28 22:10:00.000000

V1.3 Phase 2 — Member 3: add the `source` provenance column to
template_fields (detected/cleaned/manual/ai) so fields created via cleaning
(Phase 2), the field editor (Phase 3), and AI suggestions (Phase 4) can be
distinguished from Phase 1 detection. Additive only: NOT NULL with
server_default 'detected' so existing rows backfill; downgrade drops it.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3f8d2c6a9e41"
down_revision = "7c4e9a1b2d58"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "template_fields",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default=sa.text("'detected'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("template_fields", "source")
