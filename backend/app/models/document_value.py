"""
DocumentValue model for V1.4 Phase 2 — stores user-entered values for each field in a document.

Each row represents a single field value for a document. Uses field_name (string)
as the key rather than field_id for resilience against template reconfiguration.
Values are stored as TEXT to accommodate textareas, JSON arrays for list fields,
and string representations of all primitive types.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentValue(Base):
    __tablename__ = "document_values"

    __table_args__ = (
        UniqueConstraint("document_id", "field_name", name="uq_document_value_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
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

    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="values")
