"""
Document endpoints for V1.4 Phase 2 — Save Draft functionality.

Endpoints:
- POST /documents/create
- PUT /documents/{document_id}/values
- GET /documents
- GET /documents/{document_id}
- GET /documents/{document_id}/values
"""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import CurrentUser, DbSession
from app.crud.document_crud import (
    create_document,
    delete_document,
    get_document_by_id,
    get_documents_by_user,
)
from app.crud.document_value_crud import get_values_by_document, upsert_values
from app.crud.template_crud import get_template_by_id
from app.crud.template_field_crud import get_fields_by_template
from app.models.document import Document
from app.models.template import Template
from app.schemas.document import (
    DocumentCreate,
    DocumentListItem,
    DocumentRead,
    DocumentValuesBulkRead,
    DocumentValuesBulkUpsert,
)
from app.services.document_validator import validate_document_values
from app.services.template_access import user_can_view_template

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter()


@router.post(
    "/create",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document draft from a template",
)
def create_document_endpoint(
    db: DbSession,
    current_user: CurrentUser,
    payload: DocumentCreate,
):
    """
    Create a new document draft.

    - Validates template exists and user has view access
    - Auto-generates name if not provided: "{template.name} Draft - {timestamp}"
    - Returns DocumentRead with empty values list
    """
    # Check template exists
    template = get_template_by_id(db, payload.template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Check user can view template
    if not user_can_view_template(current_user, template):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this template",
        )

    # Auto-generate name if not provided
    name = payload.name
    if name is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        name = f"{template.name} Draft - {timestamp}"

    # Create document
    document = create_document(
        db=db,
        template_id=payload.template_id,
        created_by=current_user.id,
        name=name,
        status="draft",
    )

    # Return with empty values (DocumentRead expects values field)
    return DocumentRead(
        id=document.id,
        template_id=document.template_id,
        created_by=document.created_by,
        name=document.name,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        values=[],
    )


@router.put(
    "/{document_id}/values",
    response_model=DocumentValuesBulkRead,
    summary="Save/upsert form values for a document draft",
)
def save_document_values(
    db: DbSession,
    current_user: CurrentUser,
    document_id: int,
    payload: DocumentValuesBulkUpsert,
):
    """
    Validate and upsert field values for a document draft.

    - Enforces ownership (created_by == current_user.id)
    - Validates against template fields: required, type (number, email), validation_rule
    - Returns saved values on success
    """
    # Load document
    document = get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Enforce ownership
    if document.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own drafts",
        )

    # Load template and fields for validation
    template = get_template_by_id(db, document.template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    fields = get_fields_by_template(db, document.template_id)

    # Validate values
    values_to_save = [v.model_dump() for v in payload.values]
    validate_document_values(fields, values_to_save)

    # Upsert values
    saved_values = upsert_values(db, document_id, values_to_save)

    # Return saved values
    return DocumentValuesBulkRead(
        document_id=document_id,
        values=[
            {
                "id": v.id,
                "document_id": v.document_id,
                "field_name": v.field_name,
                "value": v.value,
                "created_at": v.created_at,
                "updated_at": v.updated_at,
            }
            for v in saved_values
        ],
    )


@router.get(
    "",
    response_model=list[DocumentListItem],
    summary="List current user's document drafts",
)
def list_user_documents(
    db: DbSession,
    current_user: CurrentUser,
):
    """
    List all documents created by the current user.

    - Ordered by updated_at desc (newest first)
    - Includes template_name for display
    """
    documents = get_documents_by_user(db, current_user.id)

    # Enrich with template_name
    template_ids = [d.template_id for d in documents]
    templates = (
        db.execute(select(Template).where(Template.id.in_(template_ids)))
        .scalars()
        .all()
    )
    template_map = {t.id: t.name for t in templates}

    return [
        DocumentListItem(
            id=d.id,
            template_id=d.template_id,
            template_name=template_map.get(d.template_id, "Unknown"),
            name=d.name,
            status=d.status,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in documents
    ]


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Get a document draft with values",
)
def get_document(
    db: DbSession,
    current_user: CurrentUser,
    document_id: int,
):
    """
    Get a document draft with its saved values.

    - Enforces ownership (created_by == current_user.id)
    - Returns DocumentRead with joined values
    """
    document = get_document_by_id(db, document_id, include_values=True)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Enforce ownership
    if document.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own drafts",
        )

    # Build response with values
    return DocumentRead(
        id=document.id,
        template_id=document.template_id,
        created_by=document.created_by,
        name=document.name,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        values=[
            {
                "id": v.id,
                "document_id": v.document_id,
                "field_name": v.field_name,
                "value": v.value,
                "created_at": v.created_at,
                "updated_at": v.updated_at,
            }
            for v in document.values
        ],
    )


@router.get(
    "/{document_id}/values",
    response_model=DocumentValuesBulkRead,
    summary="Get just the values for a document draft",
)
def get_document_values(
    db: DbSession,
    current_user: CurrentUser,
    document_id: int,
):
    """
    Get just the values array for a document draft (used by edit mode).

    - Enforces ownership
    - Returns values without full document metadata
    """
    document = get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Enforce ownership
    if document.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own drafts",
        )

    values = get_values_by_document(db, document_id)

    return DocumentValuesBulkRead(
        document_id=document_id,
        values=[
            {
                "id": v.id,
                "document_id": v.document_id,
                "field_name": v.field_name,
                "value": v.value,
                "created_at": v.created_at,
                "updated_at": v.updated_at,
            }
            for v in values
        ],
    )
