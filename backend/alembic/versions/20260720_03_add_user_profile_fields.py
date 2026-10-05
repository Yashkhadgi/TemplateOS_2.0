"""add user profile fields

Revision ID: 20260720_03
Revises: 20260719_02
Create Date: 2026-07-20 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260720_03"
down_revision = "20260719_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("organization", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=2048), nullable=True))
    op.add_column("users", sa.Column("signature_path", sa.String(length=1024), nullable=True))
    op.add_column("users", sa.Column("preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferences")
    op.drop_column("users", "signature_path")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "phone")
    op.drop_column("users", "job_title")
    op.drop_column("users", "organization")
    op.drop_column("users", "department")
