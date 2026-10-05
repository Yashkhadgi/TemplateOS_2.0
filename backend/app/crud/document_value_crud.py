"""
CRUD helpers for document_values (V1.4 Phase 2 — Member 3).

Member 2's endpoints call these:
- upsert_values            -> PUT /documents/{id}/values
- get_values_by_document   -> GET /documents/{id}/values
- delete_values_by_document -> cascade delete (called by document_crud.delete_document)
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.document_value import DocumentValue


def upsert_values(
    db: Session, document_id: int, values: list[dict]
) -> list["DocumentValue"]:
    """
    Upsert multiple field values for a document.

    For each {field_name, value} in values:
    - If row exists (document_id, field_name), update value + updated_at.
    - If not, insert new row.
    Commit once at the end.
    Return all upserted rows.
    """
    from app.models.document_value import DocumentValue

    result = []
    for val in values:
        field_name = val["field_name"]
        value_text = val["value"]

        existing = db.execute(
            select(DocumentValue).where(
                DocumentValue.document_id == document_id,
                DocumentValue.field_name == field_name,
            )
        ).scalar_one_or_none()

        if existing:
            existing.value = value_text
            existing.updated_at = datetime.utcnow()
            result.append(existing)
        else:
            new_val = DocumentValue(
                document_id=document_id, field_name=field_name, value=value_text
            )
            db.add(new_val)
            result.append(new_val)

    db.commit()
    for r in result:
        db.refresh(r)
    return result


def get_values_by_document(db: Session, document_id: int) -> list["DocumentValue"]:
    """
    Return all values for a document (no specific order).
    """
    from app.models.document_value import DocumentValue

    result = db.execute(
        select(DocumentValue).where(DocumentValue.document_id == document_id)
    )
    return list(result.scalars().all())


def delete_values_by_document(db: Session, document_id: int) -> int:
    """
    Delete all values for a document.
    Returns the number of rows deleted.
    """
    from app.models.document_value import DocumentValue

    from sqlalchemy import delete

    result = db.execute(
        delete(DocumentValue).where(DocumentValue.document_id == document_id)
    )
    db.commit()
    return result.rowcount or 0
