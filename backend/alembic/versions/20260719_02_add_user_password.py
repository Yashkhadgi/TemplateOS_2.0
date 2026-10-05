"""add user password hash

Revision ID: 20260719_02
Revises: 20260713_01
Create Date: 2026-07-19 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719_02"
down_revision = "20260713_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
