"""add_ai_generations_table

Revision ID: e5f2a8c6d4b7
Revises: b9e5d2c8a740
Create Date: 2026-09-10 10:00:00.000000

V1.3 Phase 4 — Member 3: create the ai_generations audit table. Every AI
call (success or failure) writes one lean metadata row — action type,
model, template, acting user, status, suggestion count. No prompt/output
bodies are stored (detail is a tiny optional note).

Cross-dialect notes:
- created_at uses server_default sa.text("CURRENT_TIMESTAMP") (works on
  PostgreSQL and SQLite).
- status uses server_default sa.text("'success'").
- template_id -> templates.id ON DELETE SET NULL: the audit trail
  survives template deletion.
- created_by -> users.id ON DELETE CASCADE.
- document_id is RESERVED for V1.4 (documents table does not exist yet)
  and deliberately has NO foreign key — plain nullable Integer.
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e5f2a8c6d4b7"
down_revision = "b9e5d2c8a740"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_generations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("field_key", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'success'"),
            nullable=False,
        ),
        sa.Column("suggestions_count", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_generations_template_id"),
        "ai_generations",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_generations_created_by"),
        "ai_generations",
        ["created_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_generations_created_by"), table_name="ai_generations")
    op.drop_index(op.f("ix_ai_generations_template_id"), table_name="ai_generations")
    op.drop_table("ai_generations")
