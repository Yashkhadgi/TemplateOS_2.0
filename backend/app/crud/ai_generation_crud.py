"""
CRUD for ai_generations (V1.3 Phase 4 — Member 3).

- log_ai_generation: ONE lean insert per AI call (success AND error).
  Member 2's suggest-fields endpoint calls this in both paths.
- get_ai_generations_by_template: newest-first read for an AI history view.

Keyword signature is the locked Member 2 <-> Member 3 contract:
    log_ai_generation(db, *, action_type, model, template_id=None,
        created_by, field_key=None, status="success",
        suggestions_count=None, detail=None)
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_generation import AiGeneration


def log_ai_generation(
    db: Session,
    *,
    action_type: str,
    model: str,
    template_id: int | None = None,
    created_by: int,
    field_key: str | None = None,
    status: str = "success",
    suggestions_count: int | None = None,
    detail: str | None = None,
) -> AiGeneration:
    """
    Insert one audit row and return it. Keep it cheap: a single insert +
    commit + refresh, metadata only (never prompt/output bodies).
    """
    db_obj = AiGeneration(
        action_type=action_type,
        model=model,
        template_id=template_id,
        field_key=field_key,
        created_by=created_by,
        status=status,
        suggestions_count=suggestions_count,
        detail=detail,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_ai_generations_by_template(
    db: Session,
    template_id: int,
    limit: int = 50,
) -> list[AiGeneration]:
    """Return a template's AI audit rows, newest first (created_at desc, id desc)."""
    result = db.execute(
        select(AiGeneration)
        .where(AiGeneration.template_id == template_id)
        .order_by(AiGeneration.created_at.desc(), AiGeneration.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
