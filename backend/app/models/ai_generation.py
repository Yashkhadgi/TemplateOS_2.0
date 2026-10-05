"""
AiGeneration model — the AI audit trail (V1.3 Phase 4 — Member 3).

Every AI call (success OR failure) writes exactly ONE lean metadata row:
what action ran, which model, on which template, by which user, how many
suggestions came back (MD/features.md §10, §14). Prompts and full model
outputs are NEVER stored — `detail` is a tiny optional note only.

The table is a core V1 building block reused by every future AI feature
(grammar, tone, rewrite, MoM generation), not just Phase 4 suggestions.

Design notes:
- template_id ON DELETE SET NULL (chosen behavior): the audit trail
  SURVIVES template deletion — governance rows are append-only history.
- document_id is RESERVED for the V1.4 documents table and deliberately
  has NO foreign key yet (no FK to a non-existent table).
- status defaults to "success" both in Python (custom __init__, so ORM
  objects have it pre-flush) and at the DB level (server_default).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base

# Terminal state of an AI call (lean status, never bodies).
AI_STATUSES = ("success", "error")


class AiGeneration(Base):
    __tablename__ = "ai_generations"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "status" not in kwargs:
            self.status = "success"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # "suggest_fields" today; future: "improve_writing", "rewrite_tone", ...
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # The Bedrock model id used (e.g. "anthropic.claude-3-5-sonnet-...").
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # RESERVED for V1.4 documents — plain Integer, NO FK yet.
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="success", server_default="success"
    )
    suggestions_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Tiny optional note (e.g. "AI is not configured"). NEVER prompt/output dumps.
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @validates("status")
    def validate_status(self, _key: str, status: str) -> str:
        if status not in AI_STATUSES:
            raise ValueError(f"Unsupported AI generation status: {status}")
        return status
