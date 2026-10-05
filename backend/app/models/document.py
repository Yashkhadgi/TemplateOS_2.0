"""
Document model for V1.4 Phase 2 — persists form values as drafts.

A document represents a user's working draft based on a template.
It stores the template reference, creator, optional name, status,
and has a one-to-many relationship with DocumentValue for field values.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.template import Template
    from app.models.user import User
    from app.models.document_value import DocumentValue

DOCUMENT_STATUSES = ("draft", "generated", "submitted", "approved", "rejected", "final")


class Document(Base):
    __tablename__ = "documents"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "status" not in kwargs:
            self.status = "draft"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        server_default=text("'draft'"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    # Relationships
    template: Mapped["Template"] = relationship("Template", back_populates="documents")
    creator: Mapped["User"] = relationship("User", back_populates="documents")
    values: Mapped[list["DocumentValue"]] = relationship(
        "DocumentValue", back_populates="document", cascade="all, delete-orphan"
    )

    @validates("status")
    def validate_status(self, _key: str, value: str) -> str:
        if value not in DOCUMENT_STATUSES:
            raise ValueError(f"Invalid status: {value}")
        return value
