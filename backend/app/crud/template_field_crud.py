"""
CRUD helpers for template_fields (V1.3 Phase 1 — Member 3).

Member 2's detection endpoint persists through these:
- bulk_create_fields          -> first-run / force re-detect writes
- get_fields_by_template      -> ordered read (display_order, id)
- delete_fields_by_template   -> force re-detect clears old rows first
- field_exists                -> idempotency guard

V1.3 Phase 2 additions:
- next_display_order          -> append position (max + 1)
- append_field                -> idempotent single insert (cleaning)

V1.3 Phase 3 additions (field editor):
- get_field_by_id             -> single row by primary key
- create_field                -> single create with auto display_order
- update_field                -> partial update (exclude_unset)
- delete_field                -> delete + reindex to contiguous 0..n-1
- reorder_fields              -> explicit permutation reorder
- sync_fields                 -> transactional full-sync (create/update/delete)

Integrity guarantees after every mutation:
- field_name unique per template (uq_template_field_key)
- field_type in the MVP set (@validates + ck_template_field_type)
- display_order contiguous 0..n-1 (_reindex on every structural change)
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.template_field import TemplateField
from app.schemas.template_field import (
    TemplateFieldCreate,
    TemplateFieldUpdate,
    TemplateFieldUpsert,
)


def bulk_create_fields(
    db: Session,
    template_id: int,
    fields: list[TemplateFieldCreate],
) -> list[TemplateField]:
    """Bulk-insert field rows for a template and return the refreshed rows in input order."""
    if not fields:
        return []
    db_objs = [
        TemplateField(template_id=template_id, **field.model_dump()) for field in fields
    ]
    db.add_all(db_objs)
    db.commit()
    for obj in db_objs:
        db.refresh(obj)
    return db_objs


def get_fields_by_template(db: Session, template_id: int) -> list[TemplateField]:
    """Return a template's fields ordered by display_order, then id (first-seen order)."""
    result = db.execute(
        select(TemplateField)
        .where(TemplateField.template_id == template_id)
        .order_by(TemplateField.display_order, TemplateField.id)
    )
    return list(result.scalars().all())


def delete_fields_by_template(db: Session, template_id: int) -> int:
    """Delete all field rows for a template. Returns the number of rows deleted."""
    result = db.execute(
        delete(TemplateField).where(TemplateField.template_id == template_id)
    )
    db.commit()
    return result.rowcount or 0


def field_exists(db: Session, template_id: int, field_name: str) -> bool:
    """Return True if the template already has a field with the given key."""
    result = db.execute(
        select(func.count(TemplateField.id)).where(
            TemplateField.template_id == template_id,
            TemplateField.field_name == field_name,
        )
    )
    return (result.scalar() or 0) > 0


def next_display_order(db: Session, template_id: int) -> int:
    """Return the next display_order for a template (current max + 1, or 0 if none)."""
    result = db.execute(
        select(func.max(TemplateField.display_order)).where(
            TemplateField.template_id == template_id
        )
    )
    current_max = result.scalar()
    return 0 if current_max is None else current_max + 1


def append_field(
    db: Session,
    template_id: int,
    field: TemplateFieldCreate,
) -> TemplateField | None:
    """
    Append one field to a template, idempotently.

    Returns None (skips, no duplicate) if the template already has a field
    with the same key (uq_template_field_key / field_exists guard).
    display_order defaults to next_display_order when not provided.
    """
    if field_exists(db, template_id, field.field_name):
        return None
    payload = field.model_dump()
    if payload.get("display_order") in (None, 0):
        payload["display_order"] = next_display_order(db, template_id)
    db_obj = TemplateField(template_id=template_id, **payload)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


# --- V1.3 Phase 3 field editor (Member 3) ---


def _reindex(db: Session, template_id: int) -> None:
    """
    Renumber a template's fields to contiguous 0..n-1 by current
    (display_order, id). Does NOT commit — callers own the commit.
    """
    fields = get_fields_by_template(db, template_id)
    for position, field in enumerate(fields):
        field.display_order = position


def get_field_by_id(db: Session, field_id: int) -> TemplateField | None:
    """Return a field row by primary key or None."""
    return db.get(TemplateField, field_id)


def create_field(
    db: Session,
    template_id: int,
    data: TemplateFieldCreate,
) -> TemplateField:
    """
    Insert one field row. display_order honors data.display_order when
    provided (non-zero, matching append_field's convention), else appends
    via next_display_order.

    Raises ValueError on a duplicate field_name (clean pre-check; the
    uq_template_field_key constraint remains the backstop under races).
    """
    if field_exists(db, template_id, data.field_name):
        raise ValueError(
            f"Field '{data.field_name}' already exists for template {template_id}"
        )
    payload = data.model_dump()
    if payload.get("display_order") in (None, 0):
        payload["display_order"] = next_display_order(db, template_id)
    db_obj = TemplateField(template_id=template_id, **payload)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_field(
    db: Session,
    field: TemplateField,
    data: TemplateFieldUpdate,
) -> TemplateField:
    """
    Partial update: apply only provided (exclude_unset) attributes, then
    commit and refresh.

    Renaming to a key that already exists on the template raises ValueError
    (clean pre-check; the unique constraint remains the backstop).
    If display_order is provided, the template is reindexed afterwards so
    display_order stays contiguous 0..n-1 (ordering moves should normally
    go through reorder_fields / sync_fields).
    """
    payload = data.model_dump(exclude_unset=True)
    new_name = payload.get("field_name")
    if (
        new_name is not None
        and new_name != field.field_name
        and field_exists(db, field.template_id, new_name)
    ):
        raise ValueError(
            f"Field '{new_name}' already exists for template {field.template_id}"
        )
    order_touched = "display_order" in payload
    for key, value in payload.items():
        setattr(field, key, value)
    db.commit()
    if order_touched:
        _reindex(db, field.template_id)
        db.commit()
    db.refresh(field)
    return field


def delete_field(db: Session, field: TemplateField) -> None:
    """
    Delete one field and reindex the template's remaining fields to
    contiguous 0..n-1 (no gaps, no duplicates).
    """
    template_id = field.template_id
    db.delete(field)
    # Make the pending delete visible to the reindex query regardless of
    # the session's autoflush setting.
    db.flush()
    _reindex(db, template_id)
    db.commit()


def reorder_fields(
    db: Session,
    template_id: int,
    ordered_ids: list[int],
) -> list[TemplateField]:
    """
    Reorder a template's fields to the given id sequence.

    ordered_ids must be a permutation of the template's current field ids —
    missing, extra, or duplicated ids raise ValueError (Member 2 maps to
    422). Returns the fields in the new order.
    """
    current = get_fields_by_template(db, template_id)
    current_ids = {field.id for field in current}
    if len(ordered_ids) != len(current_ids) or set(ordered_ids) != current_ids:
        raise ValueError(
            "ordered_ids must be a permutation of the template's current field ids"
        )
    by_id = {field.id: field for field in current}
    for position, field_id in enumerate(ordered_ids):
        by_id[field_id].display_order = position
    db.commit()
    return get_fields_by_template(db, template_id)


def sync_fields(
    db: Session,
    template_id: int,
    items: list[TemplateFieldUpsert],
) -> list[TemplateField]:
    """
    Transactional full-sync of a template's fields:
    - items with an id update in place (only sent attributes applied)
    - items without an id create new fields
    - existing fields absent from items are deleted (full-sync semantics)
    - display_order = array index (client-supplied display_order is ignored)

    All-or-nothing: a single commit, rollback on any error. Raises
    ValueError for an id belonging to another template and for duplicate
    field_names within the payload; the unique constraint can still surface
    an IntegrityError for cross-item rename collisions. Fields created here
    default to source='manual' (editor provenance) unless stated otherwise.
    """
    try:
        existing = get_fields_by_template(db, template_id)
        by_id = {field.id: field for field in existing}

        for item in items:
            if item.id is not None and item.id not in by_id:
                raise ValueError(
                    f"Field id {item.id} does not belong to template {template_id}"
                )

        seen_names: set[str] = set()
        for item in items:
            if item.field_name in seen_names:
                raise ValueError(
                    f"Duplicate field_name in sync payload: '{item.field_name}'"
                )
            seen_names.add(item.field_name)

        kept_ids = {item.id for item in items if item.id is not None}

        # Delete absent fields first and flush, so a new field may reuse a
        # deleted field's key within the same transaction.
        for field in existing:
            if field.id not in kept_ids:
                db.delete(field)
        db.flush()

        for index, item in enumerate(items):
            if item.id is not None:
                field = by_id[item.id]
                payload = item.model_dump(
                    exclude_unset=True, exclude={"id", "display_order"}
                )
                for key, value in payload.items():
                    setattr(field, key, value)
                field.display_order = index
            else:
                payload = item.model_dump(
                    exclude={"id", "display_order"}, exclude_none=True
                )
                payload.setdefault("source", "manual")
                db.add(
                    TemplateField(
                        template_id=template_id,
                        display_order=index,
                        **payload,
                    )
                )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_fields_by_template(db, template_id)
