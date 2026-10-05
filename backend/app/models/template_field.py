"""
Template Field model for storing extracted DOCX placeholders.

V1.3 Phase 1 — expanded to the full field-metadata contract:
field_label, section, example_value, validation_rule, ai_enabled.
`field_name` is the placeholder KEY (e.g. "employee_name").
`description` is the help text shown under the field in smart forms.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.template import Template

# MVP field-type vocabulary (V1.3 spec): no "dropdown"; includes "textarea" and "list".
FIELD_TYPES = ("text", "textarea", "date", "number", "list", "signature")

# How a field came to exist (V1.3 Phase 2+): detected by Phase 1 scanning,
# created by Phase 2 cleaning, added manually in Phase 3, or suggested by AI
# in Phase 4 (audit trail for the UI and the AI-generation log).
FIELD_SOURCES = ("detected", "cleaned", "manual", "ai")


class TemplateField(Base):
    __tablename__ = "template_fields"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "field_type" not in kwargs:
            self.field_type = "text"
        if "is_required" not in kwargs:
            self.is_required = True
        if "display_order" not in kwargs:
            self.display_order = 0
        if "ai_enabled" not in kwargs:
            self.ai_enabled = False
        if "source" not in kwargs:
            self.source = "detected"

    __table_args__ = (
        UniqueConstraint("template_id", "field_name", name="uq_template_field_key"),
        Index("ix_template_fields_template_order", "template_id", "display_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    field_type: Mapped[str] = mapped_column(
        String(20), default="text", server_default="text"
    )
    default_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_required: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # V1.3 Phase 1 expansion (all nullable / safe defaults so existing rows migrate cleanly)
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    example_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    display_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # V1.3 Phase 2 addition: provenance of the field (detected/cleaned/manual/ai).
    source: Mapped[str] = mapped_column(
        String(20), default="detected", server_default="detected"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["Template"] = relationship("Template", back_populates="fields")

    @validates("field_type")
    def validate_field_type(self, _key: str, field_type: str) -> str:
        if field_type not in FIELD_TYPES:
            raise ValueError(f"Unsupported field type: {field_type}")
        return field_type

    @validates("source")
    def validate_source(self, _key: str, source: str) -> str:
        if source not in FIELD_SOURCES:
            raise ValueError(f"Unsupported field source: {source}")
        return source
