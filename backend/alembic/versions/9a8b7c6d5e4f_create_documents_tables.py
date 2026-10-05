"""create_documents_tables

Revision ID: 9a8b7c6d5e4f
Revises: e5f2a8c6d4b7
Create Date: 2026-09-13 00:00:00.000000

V1.4 Phase 2 — Member 3: create documents and document_values tables for
persisting form values as drafts.

Cross-dialect notes:
- created_at/updated_at use server_default sa.text("CURRENT_TIMESTAMP")
  (works on PostgreSQL and SQLite).
- status uses server_default sa.text("'draft'").
- documents.template_id -> templates.id ON DELETE CASCADE
- documents.created_by -> users.id ON DELETE CASCADE
- document_values.document_id -> documents.id ON DELETE CASCADE
- document_values has unique constraint uq_document_value_key (document_id, field_name)
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9a8b7c6d5e4f"
down_revision = "e5f2a8c6d4b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_documents_template_id"),
        "documents",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documents_created_by"),
        "documents",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documents_status"),
        "documents",
        ["status"],
        unique=False,
    )

    # document_values table
    op.create_table(
        "document_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "field_name", name="uq_document_value_key"),
    )
    op.create_index(
        op.f("ix_document_values_document_id"),
        "document_values",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_values_document_id"), table_name="document_values")
    op.drop_table("document_values")
    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_created_by"), table_name="documents")
    op.drop_index(op.f("ix_documents_template_id"), table_name="documents")
    op.drop_table("documents")
